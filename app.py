# app.py (GeniusMind Production Hardening v2)

import os
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
import yfinance as yf
import requests
import google.generativeai as genai
import json
import re # Import regular expressions

# Load environment variables from a .env file
load_dotenv()
app = Flask(__name__)

# --- API Key Configuration ---
FMP_API_KEY = os.getenv("FMP_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=GEMINI_API_KEY)


def get_candidate_stocks(query, country):
    """
    NEW HARDENED ENGINE: Intelligently fetches a list of candidate stocks.
    Now includes price screening directly from the query.
    """
    print(f"--- Starting Hardened Screening for Country: {country} ---")
    base_url = f"https://financialmodelingprep.com/api/v3/stock-screener?country={country}&apikey={FMP_API_KEY}"
    
    # Use regular expressions to find a price limit in the query
    price_match = re.search(r'(under|less than|below|upto)\s*(\d+)', query)
    
    if price_match:
        price_limit = price_match.group(2)
        print(f"INFO: Price limit found in query: under {price_limit}. Applying filter.")
        screener_url = f"{base_url}&priceLowerThan={price_limit}&volumeMoreThan=50000&limit=50"
    elif "penny" in query or "small cap" in query:
        print("INFO: 'Penny Stock' keyword detected. Adjusting screener for small caps.")
        screener_url = f"{base_url}&priceLowerThan=100&marketCapLowerThan=20000000000&volumeMoreThan=50000&limit=50"
    else:
        print("INFO: Defaulting to standard large-cap, liquid stock screening.")
        screener_url = f"{base_url}&marketCapMoreThan=50000000000&volumeMoreThan=100000&limit=50"

    print(f"DEBUG: Calling FMP Screener URL: {screener_url}")
    response = requests.get(screener_url, timeout=10) # Added a 10-second timeout
    
    if response.status_code != 200 or not response.json():
        print(f"ERROR: FMP Screener API call failed. Status: {response.status_code}")
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
        country = "IN" if "indian" in user_query else "US"
        candidate_stocks = get_candidate_stocks(user_query, country)
        if not candidate_stocks:
            return jsonify([{"ticker": "SYSTEM", "company_name": "No Stocks Found", "reason": "My initial screening based on your specific criteria (like price, market cap, etc.) did not find any matching stocks to analyze. Please try a broader request."}])

        quant_profiles = []
        for ticker in candidate_stocks[:20]: # Widen analysis pool
            print(f"--- Aggregating data for {ticker} ---")
            profile = {"ticker": ticker}
            try:
                # --- FAULT-TOLERANT DATA AGGREGATION ---
                yf_ticker_str = f"{ticker}.NS" if country == "IN" and '.' not in ticker else ticker
                yf_data = yf.Ticker(yf_ticker_str)
                info = yf_data.info
                
                # Gracefully handle missing yfinance data
                profile["companyName"] = info.get('longName', "N/A")
                profile["sector"] = info.get('sector', "N/A")
                profile["marketCap"] = info.get('marketCap')
                profile["pegRatio"] = info.get('pegRatio')
                profile["profitMargin"] = info.get('profitMargins')
                profile["revenueGrowth"] = info.get('revenueGrowth')

                # Gracefully handle missing FMP data
                ratios_url = f"https://financialmodelingprep.com/api/v3/ratios-ttm/{ticker}?apikey={FMP_API_KEY}"
                ratios_response = requests.get(ratios_url, timeout=10)
                ratios = ratios_response.json()[0] if ratios_response.status_code == 200 and ratios_response.json() else {}
                
                profile["peRatio"] = ratios.get('priceEarningsRatioTTM')
                profile["priceToSalesRatio"] = ratios.get('priceToSalesRatioTTM')
                profile["returnOnEquity"] = ratios.get('returnOnEquityTTM')
                profile["debtToEquityRatio"] = ratios.get('debtToEquityRatioTTM')
                
                # Only add profile if it has at least a name and market cap
                if profile.get("marketCap"):
                    quant_profiles.append(profile)
                    print(f"SUCCESS: Profile for {ticker} created.")
                else:
                    print(f"SKIPPED: {ticker} due to missing critical data (marketCap).")

            except Exception as e:
                print(f"ERROR: Could not process data for {ticker}. Reason: {e}")
                continue

        if not quant_profiles:
             return jsonify([{"ticker": "SYSTEM", "company_name": "Data Fetch Failed", "reason": "I found a list of stocks, but I was unable to retrieve detailed financial data for them. This often happens with very small stocks or due to temporary issues with data providers."}])

        print(f"SUCCESS: Assembled {len(quant_profiles)} profiles for AI analysis.")
        
        # --- AI Analysis Step (unchanged) ---
        model = genai.GenerativeModel('gemini-2.5-flash')
        prompt = f"Act as a senior Quantitative Financial Analyst... Your user's goal is '{user_query}'. Analyze these stocks: {json.dumps(quant_profiles, indent=2)} ... You MUST select the top 3-4 stocks and provide a data-driven reason citing at least two metrics. Format as a valid JSON array of objects with keys: 'ticker', 'company_name', 'reason'."
        
        response = model.generate_content(prompt)
        cleaned_response = response.text.strip().replace('```json', '').replace('```', '').strip()
        
        try:
            parsed_json = json.loads(cleaned_response)
            return jsonify(parsed_json)
        except json.JSONDecodeError:
            return jsonify([{"ticker": "SYSTEM", "company_name": "AI Error", "reason": "The AI analysis module failed to return a valid response. This may be a temporary issue."}])

    except Exception as e:
        print(f"FATAL ERROR in main process: {e}")
        return jsonify({"error": "A fatal internal server error occurred."}), 500

# get_stock_details endpoint remains the same
@app.route('/api/get_stock_details/<string:ticker>')
def get_stock_details(ticker):
    try:
        profile_url = f"https://financialmodelingprep.com/api/v3/profile/{ticker}?apikey={FMP_API_KEY}"
        response = requests.get(profile_url, timeout=10)
        if response.status_code != 200 or not response.json():
            return jsonify({"error": "Could not retrieve FMP data."}), 404
        data = response.json()[0]
        return jsonify({
            "ticker": data.get('symbol'), "companyName": data.get('companyName'),
            "sector": data.get('sector'), "industry": data.get('industry'),
            "website": data.get('website'), "description": data.get('description'),
            "marketCap": data.get('mktCap'),
        })
    except Exception as e:
        print(f"Error in get_stock_details: {e}")
        return jsonify({"error": "An internal error occurred."}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)