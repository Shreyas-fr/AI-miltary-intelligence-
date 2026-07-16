import pandas as pd
import numpy as np
import os
import joblib

from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, TargetEncoder
from sklearn.impute import SimpleImputer
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix

# ---------------------------------------------------
# Create models folder
# ---------------------------------------------------
os.makedirs("models", exist_ok=True)

# ---------------------------------------------------
# Load Dataset
# ---------------------------------------------------
print("Loading GTD Dataset...")
df = pd.read_csv("data/globalterrorism.csv", encoding="latin1", low_memory=False)
print("Original Shape:", df.shape)

# ---------------------------------------------------
# Select Features
# ---------------------------------------------------
features = [
    "country_txt",
    "region_txt",
    "weaptype1_txt",
    "targtype1_txt",
    "gname",
    "success",
    "suicide",
    "nkill",
    "nwound"
]
target = "attacktype1_txt"

# Include time features for sorting if they exist
time_cols = [c for c in ["iyear", "imonth", "iday"] if c in df.columns]
df = df[time_cols + features + [target]].copy()

# ---------------------------------------------------
# Time-Series Split (Prevent Data Leakage)
# ---------------------------------------------------
if time_cols:
    df = df.sort_values(by=time_cols)

X = df[features]
y = df[target]

# Split sequentially (80% train, 20% test)
split_idx = int(len(X) * 0.8)
X_train, X_test = X.iloc[:split_idx].copy(), X.iloc[split_idx:].copy()
y_train, y_test = y.iloc[:split_idx].copy(), y.iloc[split_idx:].copy()

# ---------------------------------------------------
# Handle Missing Values (Imputation)
# ---------------------------------------------------
# Impute categorical features with 'Unknown'
cat_cols = ["country_txt", "region_txt", "weaptype1_txt", "targtype1_txt", "gname"]
cat_imputer = SimpleImputer(strategy="constant", fill_value="Unknown")
X_train[cat_cols] = cat_imputer.fit_transform(X_train[cat_cols])
X_test[cat_cols] = cat_imputer.transform(X_test[cat_cols])

# Impute numerical features with median
num_cols = ["success", "suicide", "nkill", "nwound"]
num_imputer = SimpleImputer(strategy="median")
X_train[num_cols] = num_imputer.fit_transform(X_train[num_cols])
X_test[num_cols] = num_imputer.transform(X_test[num_cols])

print("After Imputation, Train Shape:", X_train.shape)

# ---------------------------------------------------
# Encode Target (LabelEncoder is valid for the target)
# ---------------------------------------------------
target_encoder = LabelEncoder()
target_encoder.fit(y)
y_train = target_encoder.transform(y_train)
y_test = target_encoder.transform(y_test)

# ---------------------------------------------------
# Encode Features (Target Encoding)
# ---------------------------------------------------
# Target encoding handles high cardinality nominal variables without artificial ordinality
target_feature_encoder = TargetEncoder(target_type="multiclass", random_state=42)

cat_encoded_train = target_feature_encoder.fit_transform(X_train[cat_cols], y_train)
cat_encoded_test = target_feature_encoder.transform(X_test[cat_cols])

X_train_final = np.hstack([cat_encoded_train, X_train[num_cols].values])
X_test_final = np.hstack([cat_encoded_test, X_test[num_cols].values])

# ---------------------------------------------------
# Train Random Forest
# ---------------------------------------------------
print("Training Model...")
# class_weight="balanced" helps mitigate the highly imbalanced nature of terrorism data
model = RandomForestClassifier(
    n_estimators=100,
    n_jobs=-1,
    class_weight="balanced"
)

model.fit(X_train_final, y_train)

# ---------------------------------------------------
# Prediction & Evaluation
# ---------------------------------------------------
pred = model.predict(X_test_final)
accuracy = accuracy_score(y_test, pred)

print("\n" + "="*50)
print(f"Accuracy: {accuracy:.4f}")
print("="*50)
print("Classification Report")
print("="*50)
print(classification_report(y_test, pred))

# ---------------------------------------------------
# Save Models & Preprocessors
# ---------------------------------------------------
joblib.dump(model, "models/attack_prediction_model.pkl")
joblib.dump(target_encoder, "models/target_encoder.pkl")
joblib.dump(target_feature_encoder, "models/target_feature_encoder.pkl")
joblib.dump(cat_imputer, "models/cat_imputer.pkl")
joblib.dump(num_imputer, "models/num_imputer.pkl")

print("\n" + "="*50)
print("Model and preprocessors saved successfully")
print("="*50)
