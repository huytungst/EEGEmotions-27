# Author: Phuong Huy Tung et al., 2025

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any, Dict, Tuple

import joblib
import numpy as np
import pandas as pd
from sklearn.feature_selection import VarianceThreshold
from sklearn.impute import SimpleImputer
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
)
from sklearn.model_selection import GroupShuffleSplit
from sklearn.preprocessing import (
    LabelEncoder,
    MaxAbsScaler,
    MinMaxScaler,
    QuantileTransformer,
    RobustScaler,
    StandardScaler,
)
from tabpfn_extensions.many_class.many_class_classifier import ManyClassClassifier
from tabpfn_extensions.post_hoc_ensembles.sklearn_interface import AutoTabPFNClassifier

os.environ["OMP_NUM_THREADS"] = "1"

## ------------------------------ Configuration ----------------------------- ##

SCALERS = {
    "robust": RobustScaler,
    "standard": StandardScaler,
    "minmax": MinMaxScaler,
    "quantile": lambda: QuantileTransformer(output_distribution="normal", random_state=42),
    "maxabs": MaxAbsScaler,
}


## ------------------------------- Core Functions ------------------------------- ##


def parse_args() -> argparse.Namespace:
    """Parses command-line arguments."""
    p = argparse.ArgumentParser(
        description="EEG classification with AutoTabPFN, supporting group-aware splits and scaling."
    )
    p.add_argument("--input_csv", required=True, help="Path to EEG features CSV")
    p.add_argument("--target", default="Emo_Label_Cowen(27)", help="Name of target label column")
    p.add_argument("--group", default="ParticipantID", help="Grouping column name for data splitting")
    p.add_argument(
        "--scaler",
        default="robust",
        choices=["robust", "standard", "minmax", "quantile", "maxabs", "none"],
        help="Feature-scaling strategy",
    )
    p.add_argument(
        "--scaler_scope",
        default="global",
        choices=["global", "group"],
        help="Scale features globally or per group (participant)",
    )
    p.add_argument("--random_state", type=int, default=42, help="Random seed for reproducibility")
    p.add_argument("--max_time", type=int, default=50, help="AutoTabPFN time budget (seconds)")
    p.add_argument("--alphabet_size", type=int, default=10, help="ECOC alphabet size for ManyClassClassifier")
    p.add_argument("--n_estimators", type=int, default=20, help="Number of ECOC classifiers")
    p.add_argument("--n_redundancy", type=int, default=3, help="ECOC redundancy factor")
    p.add_argument("--val_size", type=float, default=0.1, help="Fraction for validation set (0 to disable)")
    p.add_argument("--test_size", type=float, default=0.1, help="Fraction for test set")
    p.add_argument("--include_demographics", action="store_true", help="Include demographic features")
    p.add_argument("--output_dir", default="results", help="Directory to save models and reports")
    return p.parse_args()


def load_and_prepare_data(
    csv_path: str, target_col: str, group_col: str, include_demographics: bool
) -> Tuple[pd.DataFrame, np.ndarray, np.ndarray, LabelEncoder]:
    """Loads CSV, separates features, target, and groups, and encodes labels."""
    df = pd.read_csv(csv_path)
    if target_col not in df.columns:
        raise ValueError(f"Target column '{target_col}' not found.")
    if group_col not in df.columns:
        raise ValueError(f"Group column '{group_col}' not found.")

    # Define columns to drop from features
    other_labels = [c for c in df.columns if c.startswith("Emo_Label_") and c != target_col]
    demographic_cols = ["eeg_component_number", "Age", "Gender", "Nation"]
    id_cols = ["ParticipantName", group_col]
    
    feature_cols_to_drop = id_cols
    if not include_demographics:
        feature_cols_to_drop.extend(demographic_cols)
    else:
        cat_cols = [c for c in ["Gender", "Nation"] if c in df.columns]
        if cat_cols:
            df = pd.get_dummies(df, columns=cat_cols, drop_first=False)

    X = df.drop(columns=[target_col] + other_labels + feature_cols_to_drop, errors="ignore").select_dtypes(include=np.number)
    y, groups = df[target_col].values, df[group_col].values
    
    le = LabelEncoder()
    y_encoded = le.fit_transform(y)

    print(f"Loaded data with {X.shape[1]} features and {len(le.classes_)} classes.")
    return X, y_encoded, groups, le


def split_data(
    X: pd.DataFrame, y: np.ndarray, groups: np.ndarray, test_size: float, val_size: float, random_state: int
) -> Dict[str, np.ndarray]:
    """Performs group-aware splits for train, validation, and test sets."""
    if test_size <= 0 or val_size < 0 or test_size + val_size >= 1:
        raise ValueError("Invalid split sizes. Require test_size > 0, val_size >= 0, and test+val < 1.")

    gss_test = GroupShuffleSplit(n_splits=1, test_size=test_size, random_state=random_state)
    train_val_idx, test_idx = next(gss_test.split(X, y, groups))

    indices = {"test": test_idx}
    if val_size > 0:
        relative_val_size = val_size / (1.0 - test_size)
        gss_val = GroupShuffleSplit(n_splits=1, test_size=relative_val_size, random_state=random_state)
        train_idx_rel, val_idx_rel = next(gss_val.split(X.iloc[train_val_idx], y[train_val_idx], groups[train_val_idx]))
        indices["train"], indices["val"] = train_val_idx[train_idx_rel], train_val_idx[val_idx_rel]
    else:
        indices["train"], indices["val"] = train_val_idx, np.array([], dtype=int)
    
    print(f"Split sizes -> Train: {len(indices['train'])}, Val: {len(indices['val'])}, Test: {len(indices['test'])}")
    return indices


def preprocess_features(
    X_df: pd.DataFrame, groups: np.ndarray, indices: Dict[str, np.ndarray], scaler_name: str, scaler_scope: str
) -> Tuple[Dict[str, np.ndarray], SimpleImputer, VarianceThreshold]:
    """Applies imputation, scaling, and variance thresholding to feature sets."""
    X_train_df, X_val_df, X_test_df = (X_df.iloc[indices[s]] for s in ["train", "val", "test"])
    
    # 1. Imputation
    imputer = SimpleImputer(strategy="mean")
    X_train_imp = imputer.fit_transform(X_train_df)
    X_val_imp = imputer.transform(X_val_df) if not X_val_df.empty else np.array([])
    X_test_imp = imputer.transform(X_test_df)
    
    # 2. Scaling
    if scaler_name == "none":
        X_train_scaled, X_val_scaled, X_test_scaled = X_train_imp, X_val_imp, X_test_imp
    elif scaler_scope == "global":
        scaler = SCALERS[scaler_name]()
        X_train_scaled = scaler.fit_transform(X_train_imp)
        X_val_scaled = scaler.transform(X_val_imp) if not X_val_df.empty else np.array([])
        X_test_scaled = scaler.transform(X_test_imp)
    else:  # Per-group scaling
        all_imp = np.concatenate([d for d in (X_train_imp, X_val_imp, X_test_imp) if d.size > 0])
        all_idx = np.concatenate([d.index for d in (X_train_df, X_val_df, X_test_df) if not d.empty])
        
        all_imp_df = pd.DataFrame(all_imp, index=all_idx, columns=X_df.columns)
        all_imp_df['group'] = pd.Series(groups, index=X_df.index)
        
        # Apply a new scaler to each participant's data
        def scale_group(data):
            return SCALERS[scaler_name]().fit_transform(data.drop(columns='group'))
        
        scaled_data = all_imp_df.groupby('group').apply(scale_group)
        X_scaled_df = pd.DataFrame(np.vstack(scaled_data.values), index=scaled_data.index.get_level_values(1), columns=X_df.columns)
        
        X_train_scaled = X_scaled_df.loc[X_train_df.index].values
        X_val_scaled = X_scaled_df.loc[X_val_df.index].values if not X_val_df.empty else np.array([])
        X_test_scaled = X_scaled_df.loc[X_test_df.index].values

    # 3. Variance Threshold
    selector = VarianceThreshold(threshold=0.0)
    processed_X = {
        "train": selector.fit_transform(X_train_scaled),
        "val": selector.transform(X_val_scaled) if X_val_scaled.size > 0 else np.array([]),
        "test": selector.transform(X_test_scaled),
    }
    
    final_features = processed_X["train"].shape[1]
    print(f"Features reduced by variance threshold: {X_train_scaled.shape[1]} -> {final_features}")
    return processed_X, imputer, selector


def build_classifier(n_classes: int, args: argparse.Namespace) -> Any:
    """Initializes the appropriate classifier based on the number of classes."""
    autotabpfn_config = {
        "device": "cuda",
        "max_time": args.max_time,
        "ignore_pretraining_limits": True,
        "preset": "avoid_overfitting",
    }
    if n_classes <= 10:
        print("Using AutoTabPFNClassifier (<=10 classes).")
        return AutoTabPFNClassifier(**autotabpfn_config)
    
    print("Using ManyClassClassifier (>10 classes).")
    base_estimator = AutoTabPFNClassifier(**autotabpfn_config)
    return ManyClassClassifier(
        estimator=base_estimator,
        alphabet_size=args.alphabet_size,
        n_estimators=args.n_estimators,
        n_estimators_redundancy=args.n_redundancy,
        random_state=args.random_state,
        verbose=1,
    )


def evaluate_and_report(
    model: Any, X: np.ndarray, y_true: np.ndarray, le: LabelEncoder, set_name: str, out_dir: Path, 
    groups: np.ndarray, group_col: str
) -> Dict[str, float]:
    """Predicts, evaluates, and saves reports for a given data set."""
    print(f"\nEvaluating on {set_name} set...")
    y_pred = model.predict(X)
    
    metrics = {
        "accuracy": accuracy_score(y_true, y_pred),
        "balanced_accuracy": balanced_accuracy_score(y_true, y_pred),
        "macro_f1": f1_score(y_true, y_pred, average="macro"),
    }
    print(f"{set_name.capitalize()} Accuracy: {metrics['accuracy']:.4f}")
    
    # Generate, print, and save classification report
    report_str = classification_report(y_true, y_pred, target_names=le.classes_, digits=4)
    print(report_str)
    report_dict = classification_report(y_true, y_pred, output_dict=True)
    pd.DataFrame(report_dict).T.to_csv(out_dir / f"classification_report_{set_name}.csv")

    # Save confusion matrix and predictions
    cm = confusion_matrix(y_true, y_pred)
    pd.DataFrame(cm, index=le.classes_, columns=le.classes_).to_csv(out_dir / f"confusion_matrix_{set_name}.csv")
    pd.DataFrame({
        group_col: groups,
        "y_true": le.inverse_transform(y_true),
        "y_pred": le.inverse_transform(y_pred),
    }).to_csv(out_dir / f"predictions_{set_name}.csv", index=False)

    # Save class probabilities if available
    if hasattr(model, "predict_proba"):
        try:
            np.save(out_dir / f"probabilities_{set_name}.npy", model.predict_proba(X))
        except Exception as e:
            print(f"Could not save probabilities for {set_name} set: {e}")
            
    return metrics


def save_model_artifacts(model: Any, le: LabelEncoder, out_dir: Path):
    """Saves the trained model and label encoder to disk."""
    joblib.dump(model, out_dir / "model.joblib")
    joblib.dump(le, out_dir / "label_encoder.joblib")
    
    # Optional: Save to a generic /model directory for containerized environments
    try:
        model_dir = Path("/model")
        model_dir.mkdir(parents=True, exist_ok=True)
        joblib.dump(model, model_dir / "model.joblib")
        joblib.dump(le, model_dir / "label_encoder.joblib")
        print(f"Model also saved to -> {model_dir.resolve()}")
    except OSError as e:
        print(f"Could not save model to /model directory: {e}")


## -------------------------------- Main Execution -------------------------------- ##


def main():
    """Main execution pipeline."""
    args = parse_args()
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    
    # 1. Load and prepare data
    X_df, y_enc, groups, le = load_and_prepare_data(
        args.input_csv, args.target, args.group, args.include_demographics
    )

    # 2. Split data into train, validation, and test sets
    indices = split_data(X_df, y_enc, groups, args.test_size, args.val_size, args.random_state)
    
    # 3. Preprocess features (impute, scale, select)
    processed_X, _, _ = preprocess_features(
        X_df, groups, indices, args.scaler, args.scaler_scope
    )

    # 4. Build the appropriate classifier
    model = build_classifier(len(le.classes_), args)

    # 5. Train the model
    print("\nTraining model...")
    model.fit(processed_X["train"], y_enc[indices["train"]])
    
    # 6. Evaluate and save results
    all_metrics = []
    if args.val_size > 0:
        val_metrics = evaluate_and_report(
            model, processed_X["val"], y_enc[indices["val"]], le, "val", out_dir,
            groups=groups[indices["val"]], group_col=args.group
        )
        val_metrics["set"] = "val"
        all_metrics.append(val_metrics)
    
    test_metrics = evaluate_and_report(
        model, processed_X["test"], y_enc[indices["test"]], le, "test", out_dir,
        groups=groups[indices["test"]], group_col=args.group
    )
    test_metrics["set"] = "test"
    all_metrics.append(test_metrics)

    pd.DataFrame(all_metrics).to_csv(out_dir / "metrics_summary.csv", index=False)

    # 7. Save the final model artifacts
    save_model_artifacts(model, le, out_dir)
    print(f"\nAll artifacts saved to -> {out_dir.resolve()}")


if __name__ == "__main__":
    main()