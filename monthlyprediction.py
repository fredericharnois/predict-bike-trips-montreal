import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from statsmodels.tsa.arima.model import ARIMA
from pmdarima import auto_arima
from sklearn.metrics import mean_absolute_error, mean_squared_error
import numpy as np
import glob
import os

# Create a directory for the plots if it doesn't exist
if not os.path.exists('plots'):
    os.makedirs('plots')

# Get all CSV files
all_files = glob.glob("comptage_velo_*.csv")

# Read and concatenate all CSV files
df_list = []
for filename in all_files:
    df = pd.read_csv(filename)
    year = filename.split('_')[-1].split('.')[0]  # Extract year from filename
    df['year'] = year
    df_list.append(df)

df = pd.concat(df_list, ignore_index=True)

# Define a function to clean up the time format
def fix_time_format(time_str):
    # If the time is already in HH:MM:SS format, return as is
    if len(time_str.split(':')) == 3:
        return time_str
    # If the time is in HH:MM format, append ':00' to make it HH:MM:SS
    elif len(time_str.split(':')) == 2:
        return time_str + ':00'
    return time_str

# Clean up the time format
df['datetime_str'] = df['date'] + ' ' + df['heure']
df['datetime_str'] = df['datetime_str'].apply(fix_time_format)

# Convert date and time to datetime
df['datetime'] = pd.to_datetime(df['datetime_str'], format='%Y-%m-%d %H:%M:%S', errors='coerce')

# Check if any datetime conversion failed and inspect those rows
invalid_dates = df[df['datetime'].isna()]
print(f"Invalid datetime rows:\n{invalid_dates[['datetime_str']]}")

# Aggregate data to monthly level
monthly_data = df.groupby(pd.Grouper(key='datetime', freq='M'))['nb_passages'].sum().reset_index()

# Split data into training (2019-2023) and testing (2024)
train_data = monthly_data[monthly_data['datetime'].dt.year < 2024]
test_data = monthly_data[monthly_data['datetime'].dt.year == 2024]

print(train_data.head())
print(test_data.head())

def millions_formatter(x, pos):
    return f'{x/1e6:.1f}M'

# Plot the time series
plt.figure(figsize=(12,6))
plt.plot(train_data['datetime'], train_data['nb_passages'], label='Training Data')
plt.plot(test_data['datetime'], test_data['nb_passages'], label='Test Data', color='#2ca02c')
plt.title('Monthly Bike Trips')
plt.xlabel('Date')
plt.ylabel('Number of Trips')
plt.legend()
plt.gca().yaxis.set_major_formatter(ticker.FuncFormatter(millions_formatter))
plt.savefig('plots/monthly_bike_trips.png')
plt.close()

# Prepare the training data
y = train_data['nb_passages']
y.index = train_data['datetime']

# Use auto_arima to find the best parameters
model = auto_arima(y, start_p=1, start_q=1, max_p=3, max_q=3, m=12,
                   start_P=0, seasonal=True, d=1, D=1, trace=True,
                   error_action='ignore', suppress_warnings=True, stepwise=True)

# Fit the model
model.fit(y)

print(model.summary())

# Generate predictions for 2024
n_periods = len(test_data)
fc, confint = model.predict(n_periods=n_periods, return_conf_int=True)

# Create a dataframe with the forecasts
fc_series = pd.Series(fc, index=test_data['datetime'])

# Plot the results
plt.figure(figsize=(12,6))
plt.plot(train_data['datetime'], train_data['nb_passages'], label='Training Data', color='#1f77b4')
plt.plot(test_data['datetime'], test_data['nb_passages'], label='Actual 2024 Data', color='#2ca02c')
plt.plot(fc_series.index, fc_series, color='#d62728', label='Forecast')
plt.fill_between(fc_series.index, 
                 confint[:, 0], 
                 confint[:, 1], 
                 color='#d62728', alpha=.15)
plt.title('Monthly Bike Trips - Forecast vs Actual')
plt.xlabel('Date')
plt.ylabel('Number of Trips')
plt.legend()
plt.gca().yaxis.set_major_formatter(ticker.FuncFormatter(millions_formatter))
plt.savefig('plots/forecast_vs_actual.png')
plt.close()

# Ensure alignment of fc and test_data
test_data = test_data.set_index('datetime')
fc_series = fc_series.reindex(test_data.index)

# Calculate residuals after ensuring alignment
residuals = test_data['nb_passages'] - fc_series

# Print lengths and first few values for debugging
print(f"Length of test_data['nb_passages']: {len(test_data['nb_passages'])}")
print(f"Length of fc_series: {len(fc_series)}")
print(f"First few values of test_data['nb_passages']:\n{test_data['nb_passages'].head()}")
print(f"First few values of fc_series:\n{fc_series.head()}")
print(f"Length of residuals: {len(residuals)}")

# Calculate error metrics
mae = mean_absolute_error(test_data['nb_passages'], fc_series)
rmse = np.sqrt(mean_squared_error(test_data['nb_passages'], fc_series))
mape = np.mean(np.abs((test_data['nb_passages'] - fc_series) / test_data['nb_passages'])) * 100

print(f'Mean Absolute Error: {mae}')
print(f'Root Mean Squared Error: {rmse}')
print(f'Mean Absolute Percentage Error: {mape}%')

# Plot residuals
plt.figure(figsize=(12,6))
plt.plot(test_data.index, residuals)
plt.title('Residuals')
plt.xlabel('Date')
plt.ylabel('Residual')
plt.savefig('plots/residuals.png')
plt.close()

# Plot residuals distribution
plt.figure(figsize=(12,6))
residuals.hist(bins=20)
plt.title('Distribution of Residuals')
plt.xlabel('Residual')
plt.ylabel('Frequency')
plt.savefig('plots/residuals_distribution.png')
plt.close()
