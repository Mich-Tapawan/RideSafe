import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import OneHotEncoder
from sklearn.utils.class_weight import compute_class_weight
from imblearn.over_sampling import SMOTE
from sklearn.model_selection import train_test_split
import joblib
from collections import defaultdict

class AccidentModel:
    def __init__(self):
        self.model = None
        self.encoder = None
        self.barangays = None

    def train_and_save_model(self):
        try:
            # Load datasets
            df_2022 = pd.read_excel("../traffic-incident.xlsx", sheet_name='Jan 1 - Dec 31, 2022')
            df_2023 = pd.read_excel("../traffic-incident.xlsx", sheet_name='Jan 1 - Dec 31, 2023')
            df_2024 = pd.read_excel("../traffic-incident.xlsx", sheet_name='Jan 1 - Nov 18, 2024')

            # Combine datasets and process
            df_combined = pd.concat([df_2022, df_2023, df_2024], ignore_index=True)
            df_combined['hour'] = pd.to_datetime(df_combined['timeCommitted'], format='%H:%M:%S', errors='coerce').dt.hour
            df_combined = df_combined.dropna(subset=['barangay', 'hour'])

            # Prepare complete dataset with inferred non-accidents
            all_barangays = df_combined['barangay'].unique()
            all_hours = np.arange(24)
            records = []
            for barangay in all_barangays:
                barangay_data = df_combined[df_combined['barangay'] == barangay]
                accident_hours = barangay_data['hour'].unique()
                for hour in all_hours:
                    is_accident = 1 if hour in accident_hours else 0
                    records.append((barangay, hour, is_accident))
            df_balanced = pd.DataFrame(records, columns=['barangay', 'hour', 'is_accident'])
            df_balanced['is_peak_hour'] = df_balanced['hour'].apply(lambda x: 1 if 7 <= x <= 9 or 17 <= x <= 19 else 0)

            # Encode and balance the data
            X = df_balanced[['barangay', 'hour', 'is_peak_hour']]
            y = df_balanced['is_accident']
            encoder = OneHotEncoder(sparse_output=False)
            barangay_encoded = encoder.fit_transform(X[['barangay']])
            X_encoded = np.hstack([barangay_encoded, X[['hour', 'is_peak_hour']].values])

            # Split the data into train and test sets
            X_train, X_test, y_train, y_test = train_test_split(X_encoded, y, test_size=0.2, random_state=42)

            # Apply SMOTE to only the training data
            smote = SMOTE(random_state=42)
            X_train_resampled, y_train_resampled = smote.fit_resample(X_train, y_train)

            # Train the model
            class_weights = compute_class_weight('balanced', classes=np.unique(y_train_resampled), y=y_train_resampled)
            model = RandomForestClassifier(
                n_estimators=200, max_depth=10, class_weight={i: weight for i, weight in enumerate(class_weights)}, random_state=42
            )
            model.fit(X_train_resampled, y_train_resampled)

            # Evaluate the model on the test set
            test_accuracy = model.score(X_test, y_test)
            print(f'Test accuracy: {test_accuracy:.2f}')

            # Save the model and encoder
            joblib.dump(model, "accident_prediction_model.pkl")
            joblib.dump(encoder, "barangay_encoder.pkl")

            self.model = model
            self.encoder = encoder
            self.barangays = encoder.categories_[0]

        except Exception as e:
            print(f"Error in train_and_save_model: {str(e)}")
            raise e

    def load_model(self):
        try:
            self.model = joblib.load("./scripts/accident_prediction_model.pkl")
            self.encoder = joblib.load("./scripts/barangay_encoder.pkl")
            self.barangays = self.encoder.categories_[0]
        except Exception as e:
            print(f"Error in load_model: {str(e)}")
            raise e

    def _predict_probability_value(self, barangay, hour):
        if self.model is None or self.encoder is None:
            raise ValueError("Model or encoder is not loaded. Call 'load_model' first.")
        if barangay not in self.barangays:
            raise ValueError(f"Invalid barangay: {barangay}. Available barangays: {list(self.barangays)}")

        barangay_idx = np.where(self.barangays == barangay)[0][0]
        input_data = np.zeros(len(self.barangays) + 2)
        input_data[barangay_idx] = 1
        input_data[-2:] = [hour, 1 if 7 <= hour <= 9 or 17 <= hour <= 19 else 0]

        probs = self.model.predict_proba([input_data])
        return round(probs[0][1] * 100, 2)

    def predict_accident_chance(self, barangay, hour):
        return f'{self._predict_probability_value(barangay, hour)}%'

    def predict_all_hours(self, barangay):
        return {
            str(hour).zfill(2): self._predict_probability_value(barangay, hour)
            for hour in range(24)
        }
