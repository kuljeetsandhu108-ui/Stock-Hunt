# app.py (GeniusMind Production Hotfix & Adaptive Engine)

import os
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
import yfinance as yf
import requests
import google.generativeai as genai
import json

# Load environment variables from a .env file
load_dotenv()

app = Flask(__name__)

# --- API Key Configuration ---
FMP_API_KEY = os.getenv("FMP_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Configure the Google Gemini API
genai.configure(api_key=GEMINI_API_KEY)


def get_candidate_stocks(query, country):
    """
    NEW ADAPTIVE ENGINE: Intelligently fetches a list of candidate stocks.
    Handles different query types like 'penny stocks' vs 'large cap'.
    """
    print(f"--- Starting Adaptive Screening for Country: {country} ---")
    base_url = f"https://financialmodelingprep.com/api/v3/stock-screener?country={country}&apikey={FMP_API_KEY}"
    
    # Check for specific keywords to adapt the screening strategy
    if "penny" in query or "small cap" in query:
        print("INFO: 'Penny Stock' or 'Small Cap' keyword detected. Adjusting screener.")
        # Screen for smaller, potentially higher-risk/reward stocks
        screener_url = f"{base_url}&marketCapLowerThan=20000000000&volumeMoreThan=50000&limit=40"
    else:
        print("INFO: Defaulting to standard large-cap, liquid stock screening.")
        # Default to a broad list of large, stable, and liquid companies
        screener_url = f"{base_url}&marketCapMoreThan=50000000000&volumeMoreThan=100000&limit=40"

    print(f"DEBUG: Calling FMP Screener URL: {screener_url}")
    response = requests.get(screener_url)
    
    if response.status_code != 200 or not response.json():
        print(f"ERROR: FMP Screener API call failed or returned no data. Status: {response.status_code}")
        return []
        
    stocks = response.json()
    print(f"SUCCESS: FMP Screener returned {len(stocks)} candidate stocks.")
    return [stock['symbol'] for stock in stocks]


# --- Flask Routes ---

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/get_stock_recommendation', methods=['POST'])
def get_stock_recommendation():
    try:
        user_query = request.json.get('query', '').lower()
        if not user_query:
            return jsonify({"error": "Query not provided"}), 400

        country = "IN" if "indian" in user_query else "US"
        
        # --- Step 1: Use the NEW Adaptive Screening Engine ---
        candidate_stocks = get_candidate_stocks(user_query, country)
        if not candidate_stocks:
            # This now returns a more specific error message to the frontend.
            return jsonify([{"ticker": "SYSTEM", "company_name": "Analysis Failed", "reason": "My initial screening based on your criteria (e.g., 'penny stocks' or 'large cap') did not find any matching stocks to analyze. Please try rephrasing your request."}])

        # --- Step 2: Deep Data Aggregation ---
        quant_profiles = []
        for ticker in candidate_stocks[:15]: # Analyze top 15 candidates from the larger pool
            try:
                if '.' in ticker:
                    yf_ticker_str = ticker
                else:
                    yf_ticker_str = f"{ticker}.NS" if country == "IN" else ticker
                
                yf_data = yf.Ticker(yf_ticker_str)
                info = yf_data.info
                if not info or info.get('marketCap') is None:
                    continue

                ratios_url = f"https://financialmodelingprep.com/api/v3/ratios-ttm/{ticker}?apikey={FMP_API_KEY}"
                ratios_response = requests.get(ratios_url)
                ratios = ratios_response.json()[0] if ratios_response.status_code == 200 and ratios_response.json() else {}

                profile = {
                    "ticker": ticker, "companyName": info.get('longName'), "sector": info.get('sector'),
                    "marketCap": info.get('marketCap'), "peRatio": ratios.get('priceEarningsRatioTTM'),
                    "pegRatio": info.get('pegRatio'), "priceToSalesRatio": ratios.get('priceToSalesRatioTTM'),
                    "returnOnEquity": ratios.get('returnOnEquityTTM'), "debtToEquityRatio": ratios.get('debtToEquityRatioTTM'),
                    "profitMargin": info.get('profitMargins'), "revenueGrowth": info.get('revenueGrowth')
                }
                quant_profiles.append(profile)
            except Exception:
                continue

        if not quant_profiles:
             return jsonify([{"ticker": "SYSTEM", "company_name": "Data Fetch Failed", "reason": "I found a list of stocks, but I was unable to retrieve detailed financial data for them. This might be a temporary issue with the data providers."}])

        print(f"SUCCESS: Assembled {len(quant_profiles)} detailed profiles for AI analysis.")

        # --- Step 3: High-End AI Analysis ---
        model = genai.GenerativeModel('gemini-2.5-flash')
        prompt = f"""
        Act as a senior Quantitative Financial Analyst. Your task is to perform a deep analysis of the following stocks based on the provided quantitative data and the user's investment goal. Your reasoning must be sharp, data-driven, and based on established financial principles.
        **User's Investment Goal:** "{user_query}"
        **Quantitative Stock Profiles:**
        ```json
        {json.dumps(quant_profiles, indent=2)}
        ```
        **Your Task:**
        1. **Analyze and Filter:** Scrutinize each stock's quantitative profile. Use financial indicators to evaluate how well each stock aligns with the user's goal.
        2. **Select Top 3-4 Stocks:** Choose the stocks that provide the most compelling, data-supported case.
        3. **Provide Quantitative Reasoning:** For each selected stock, write a concise, expert reason for your recommendation. **You MUST cite at least two specific data points from their profile in your reason.** For example, "Recommended for its strong growth potential, evidenced by a low PEG ratio of {{pegRatio}} and high Return on Equity of {{returnOnEquity}}."
        4. **Format the Output:** The final output MUST be a valid JSON array of objects. Do not include any text, explanation, or markdown formatting outside of the JSON structure. Each object must have the keys: "ticker", "company_name", and "reason".
        """
        response = model.generate_content(prompt)
        cleaned_response = response.text.strip().replace('```json', '').replace('```', '').strip()
        
        try:
            parsed_json = json.loads(cleaned_response)
            return jsonify(parsed_json)
        except json.JSONDecodeError:
            print(f"CRITICAL ERROR: Gemini response was not valid JSON.\nResponse:\n{cleaned_response}")
            return jsonify({"error": "The AI analysis module failed to return a valid format."}), 500

    except Exception as e:
        print(f"A critical error occurred in the main process: {e}")
        return jsonify({"error": "An internal server error occurred."}), 500

@app.route('/api/get_stock_details/<string:ticker>')
def get_stock_details(ticker):
    try:
        profile_url = f"https://financialmodelingprep.com/api/v3/profile/{ticker}?apikey={FMP_API_KEY}"
        response = requests.get(profile_url)
        if response.status_code != 200 or not response.json():
            return jsonify({"error": "Could not retrieve FMP data for this stock."}), 404
        data = response.json()[0]
        return jsonify({
            "ticker": data.get('symbol'), "companyName": data.get('companyName'),
            "sector": data.get('sector'), "industry": data.get('industry'),
            "website": data.get('website'), "description": data.get('description'),
            "marketCap": data.get('mktCap'),
        })
    except Exception as e:
        print(f"An error occurred in get_stock_details: {e}")
        return jsonify({"error": "An internal error occurred."}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)