# 🏠 House Price Prediction

A machine learning project that predicts residential home sale prices using regression models trained on 80+ features including location, size, quality, and amenities.

---

## 📊 Results

| Model | R² Score | RMSE |
|---|---|---|
| Linear Regression | 0.8719 | 0.1546 |
| XGBoost | 0.8767 | 0.1517 |

> **Best Model: XGBoost with R² Score of 0.8767 (~88% accuracy)**

---

## 🛠️ Tech Stack

- **Language:** Python 3
- **Libraries:** Pandas, NumPy, Scikit-learn, XGBoost, Matplotlib, Seaborn
- **Environment:** Jupyter Notebook

---

## 📁 Project Structure

```
house-price-prediction/
│
├── data/
│   └── train.csv               # Kaggle dataset (1460 houses, 81 features)
├── models/
│   ├── best_model.pkl          # Saved XGBoost model
│   └── scaler.pkl              # Saved StandardScaler
├── notebooks/
│   └── house_price_prediction.ipynb   # Full analysis notebook
└── README.md
```

---

## 🔍 Key Steps

### 1. Exploratory Data Analysis (EDA)
- Analyzed distribution of sale prices ($34,900 – $755,000)
- Found top features affecting price: `OverallQual` (0.79), `GrLivArea` (0.71), `GarageCars` (0.64)
- Visualized correlations using heatmap

### 2. Data Cleaning
- Dropped 5 columns with excessive missing values (Alley, PoolQC, Fence, etc.)
- Filled missing numeric values with median
- Filled missing categorical values with mode
- Result: 0 missing values

### 3. Feature Engineering
- **TotalSF** — Combined basement + 1st floor + 2nd floor area
- **HouseAge** — Age of house at time of sale
- **RemodAge** — Years since last remodel
- **HasGarage** — Binary flag for garage presence
- Log-transformed `SalePrice` to reduce skewness

### 4. Modeling
- Encoded categorical features using LabelEncoder
- Scaled features using StandardScaler
- Split data: 80% train (1168 rows) / 20% validation (292 rows)
- Trained and compared Linear Regression vs XGBoost

---

## 📈 Visualizations

- Sale Price Distribution histogram
- Correlation Heatmap of top 10 features
- Actual vs Predicted Price scatter plot

---

## 🚀 How to Run

1. Clone the repository
```bash
git clone https://github.com/sathwik-2005/house-price-prediction.git
cd house-price-prediction
```

2. Install dependencies
```bash
pip install pandas numpy matplotlib seaborn scikit-learn xgboost joblib
```

3. Download dataset from [Kaggle](https://www.kaggle.com/c/house-prices-advanced-regression-techniques) and place `train.csv` in `data/`

4. Open and run the notebook
```bash
jupyter notebook notebooks/house_price_prediction.ipynb
```

---

## 📌 Dataset

- **Source:** [Kaggle — House Prices: Advanced Regression Techniques](https://www.kaggle.com/c/house-prices-advanced-regression-techniques)
- **Size:** 1,460 rows × 81 columns
- **Target:** `SalePrice` (residential home sale price in USD)

---

## 👤 Author

**Sathwik**
B.Tech Computer Science — Vellore Institute of Technology (VIT)
GitHub: [@sathwik-2005](https://github.com/sathwik-2005)
