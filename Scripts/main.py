import pandas as pd

# Creating dataframes from json
portfolio = pd.read_json("Data/raw/portfolio.json", orient='records', lines=True)
profile = pd.read_json("Data/raw/profile.json", orient='records', lines=True)
transcript = pd.read_json("Data/raw/transcript.json", orient='records', lines=True)

# Convert channels lists into dummies
channels_dummies = portfolio["channels"].str.join('|').str.get_dummies('|')
portfolio_cleaned = pd.concat([portfolio.drop(columns={"channels"}), channels_dummies], axis=1)

# Expand value nested dictionaries into flat table
value_flat = pd.json_normalize(transcript['value'])
transcript_cleaned = pd.concat([transcript.drop("value", axis=1), value_flat], axis=1)

#Export to csv
profile.to_csv("Data/processed/profile.csv")
portfolio_cleaned.to_csv("Data/processed/portfolio.csv")
transcript_cleaned.to_csv("Data/processed/transcript.csv")
