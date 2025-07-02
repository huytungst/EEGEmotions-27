# EEGEmotions-27 Dataset

**EEGEmotions-27** is a dataset of raw EEG recordings collected during affective elicitation experiments. It contains data from 88 participants as they experienced 27 distinct emotional states while watching emotionally evocative video clips.

---

## 📁 Dataset Structure

### EEG Raw Data

- **Location**: `eeg_raw/`
- **File Format**: `{Participant_ID}_{Emotion_ID}.0.txt`
  - Example: `12_5.0.txt` → Participant 12, Emotion 5 (Anger)
- **Data Format**: Plain text EEG time series (14 channels from Emotiv X headset, sampled at 256Hz)

### Emotion ID Mapping

| Emotion ID | Emotion         |
|------------|-----------------|
| 1          | admiration      |
| 2          | adoration       |
| 3          | aesthetic       |
| 4          | amusement       |
| 5          | anger           |
| 6          | anxiety         |
| 7          | awes            |
| 8          | awkwardness     |
| 9          | boredom         |
| 10         | calmness        |
| 11         | confusion       |
| 12         | craving         |
| 13         | disgust         |
| 14         | empathic pain   |
| 15         | entrancement    |
| 16         | excitement      |
| 17         | fear            |
| 18         | horror          |
| 19         | interest        |
| 20         | joy             |
| 21         | nostalgia       |
| 22         | relief          |
| 23         | romance         |
| 24         | sadness         |
| 25         | satisfaction    |
| 26         | sexual desire   |
| 27         | surprised       |

---

### 👤 Participant Information

- **File**: `participants_info.csv`
- **Fields**:
  - `Participant ID`
  - `Gender`: 
    - `1` = Male
    - `2` = Female
  - `Age`: 
    - `2` = 20s
    - `3` = 30s
    - `4` = 40s
    - `5` = 50s
    - `6` = 60s
  - `Nation`:
    - `1` = Korean
    - `2` = Vietnamese

---

### 📌 Other Files

- `emotivX_channels_location.ced`  
  → Electrode position file for Emotiv X EEG headset (14 channels).

- `video_clips/`  
  → Contains video stimuli used for emotion elicitation.

---

## ⚖️ License

This dataset is licensed under **[CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/)**  
You are free to use, share, and adapt the data **for non-commercial purposes**, with proper attribution.

---

## 📞 Contact

For questions or collaboration, please contact huytungst@gmail.com.
