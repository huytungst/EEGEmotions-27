## Setup

Create and activate a Python virtual environment:

```bash
python3 -m venv .myenv
source .myenv/bin/activate
```

Install the required packages:

```bash
pip install tabpfn==2.0.9
```

Install TabPFN Extensions (v0.1.0):

```bash
pip install "tabpfn-extensions[all] @ git+https://github.com/huytungst/tabpfn-extensions.git"
```

---

## Training

Train an EEG emotion classification model:

```bash
python train.py \
    --input_csv eeg_features_extracted.csv \
    --target "Emo_Label_Cowen(27)" \
    --group ParticipantID \
    --scaler robust \
    --scaler_scope global \
    --random_state 42 \
    --max_time 50 \
    --alphabet_size 10 \
    --n_estimators 10 \
    --n_redundancy 5 \
    --val_size 0 \
    --test_size 0.1 \
    --include_demographics \
    --output_dir result
```

* 'eeg_features_extracted.csv' is preprocessed EEG data with extracted features from the raw EEG signals.
* Increasing n_estimators and n_redundancy can improve accuracy, but it will require more VRAM and longer training time.