import pandas as pd

# Creating dataframes from json
portfolio = pd.read_json("Data/raw_json/portfolio.json", orient='records', lines=True)
profile = pd.read_json("Data/raw_json/profile.json", orient='records', lines=True)
transcript = pd.read_json("Data/raw_json/transcript.json", orient='records', lines=True)

# Convert channels lists into dummies
channels_dummies = portfolio["channels"].str.join('|').str.get_dummies('|')
portfolio_cleaned = pd.concat([portfolio.drop(columns={"channels"}), channels_dummies], axis=1)

# Expand nested dictionaries in value column to flat table
transcript["offer id"] = transcript["value"].apply(lambda x : x.get("offer id") or x.get("offer_id")) 
transcript["reward"] = transcript["value"].apply(lambda x : x.get("reward"))
transcript["amount"] = transcript["value"].apply(lambda x : x.get("amount"))


#Export to csv
profile.to_csv("Data/raw_csv/profile.csv", index=False)
portfolio_cleaned.to_csv("Data/raw_csv/portfolio.csv", index=False)
transcript.drop("value", axis=1).to_csv("Data/raw_csv/transcript.csv", index=False)