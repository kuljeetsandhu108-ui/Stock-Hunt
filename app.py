# app.py (GeniusMind FINAL - FMP Centric Architecture)

import os
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
import requests
import google.generativeai as genai
import json
import re

# Load environment variables
load_dotenv()
app = Flask(__name__)

# --- API Key Configuration ---
FMP_API_KEY = os.getenv("FMP_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=GEMINI_API_KEY)


def get_candidate_stocks_from_fmp(query, country):
    """
    FINAL ENGINE: This engine uses ONLY the FMP API for robust screening.
    It intelligently adds financial metric filters to the initial API call.
    """
    print(f"--- FMP-Centric Screening for Country: {country} ---")
    base_url = f"https://financialmodelingprep.com/api/v3/stock-screener?country={country}&apikey={FMP_API_KEY}"
    
    # Keyword analysis for FMP parameters
    price_match = re.search(r'(under|less than|below|upto)\s*(\d+)', query)
    if price_match:
        price_limit = price_match.group(2)
        print(f"INFO: Price limit found: under {price_limit}.")
        base_url += f"&priceLowerThan={price_limit}"
    
    if "growth" in query:
        print("INFO: Growth keyword found. Filtering for positive revenue growth.")
        base_url += "&revenueGrowthMoreThan=0.05" # 5% revenue growth
        
    if "undervalued" in query or "cheap" in query:
        print("INFO: Value keyword found. Filtering for low P/E and P/B.")
        base_url += "&isActivelyTrading=true&peRatioLessThan=25&pbRatioLessThan=3"
        
    if "safe" in query or "stable" in query or "dividend" in query:
        print("INFO: Safety keyword found. Filtering for dividends and low beta.")
        base_url += "&dividendYieldMoreThan=0.01&betaLowerThan=1.2" # 1% dividend yield

    screener_url = f"{base_url}&volumeMoreThan=50000&limit=40" # Always add volume and limit
    
    print(f"DEBUG: Final FMP Screener URL: {screener_url}")
    response = requests.get(screener_url, timeout=15)
    
    if response.status_code != 200 or not response.json():
        print(f"ERROR: FMP Screener returned status {response.status_code}")
        return []
        
    stocks = response.json()
    print(f"SUCCESS: FMP Screener returned {len(stocks)} candidates.")
    return [stock['symbol'] for stock in stocks]


# --- Main Flask Routes ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/get_stock_recommendation', methods=['POST'])
def get_stock_recommendation():
    try:
        user_query = request.json.get('query', '').lower()
        country = "IN" if "indian" in user_query else "US"
        candidate_stocks = get_candidate_stocks_from_fmp(user_query, country)
        if not candidate_stocks:
            return jsonify([{"ticker": "SYSTEM", "company_name": "No Stocks Found", "reason": "My professional screening system did not find any stocks matching your specific financial criteria (e.g., price, P/E ratio, growth rate). Please try a broader request."}])

        quant_profiles = []
        for ticker in candidate_stocks[:20]:
            print(f"--- Aggregating FMP data for {ticker} ---")
            try:
                # Use FMP for ALL quantitative data
                profile_url = f"https://financialmodelingprep.com/api/v3/profile/{ticker}?apikey={FMP_API_KEY}"
                ratios_url = f"https://financialmodelingprep.com/api/v3/ratios-ttm/{ticker}?apikey={FMP_API_KEY}"
                
                profile_res = requests.get(profile_url, timeout=10)
                ratios_res = requests.get(ratios_url, timeout=10)
                
                if profile_res.status_code != 200 or not profile_res.json():
                    continue # Skip if we can't get a basic profile

                profile_data = profile_res.json()[0]
                ratios_data = ratios_res.json()[0] if ratios_res.status_code == 200 and ratios_res.json() else {}

                # Build the complete profile from our reliable API source
                profile = {
                    "ticker": profile_data.get('symbol'),
                    "companyName": profile_data.get('companyName'),
                    "sector": profile_data.get('sector'),
                    "marketCap": profile_data.get('mktCap'),
                    "peRatio": ratios_data.get('priceEarningsRatioTTM'),
                    "priceToSalesRatio": ratios_data.get('priceToSalesRatioTTM'),
                    "returnOnEquity": ratios_data.get('returnOnEquityTTM'),
                    "debtToEquityRatio": ratios_data.get('debtToEquityRatioTTM'),
                }
                quant_profiles.append(profile)
                print(f"SUCCESS: Profile for {ticker} built from FMP.")
            except Exception as e:
                print(f"ERROR: Failed during FMP data aggregation for {ticker}. Reason: {e}")
                continue

        if not quant_profiles:
             return jsonify([{"ticker": "SYSTEM", "company_name": "Data Aggregation Failed", "reason": "I found a list of stocks, but I was unable to retrieve their detailed financial profiles from the provider. This may be a temporary API issue."}])

        print(f"SUCCESS: Assembled {len(quant_profiles)} profiles for AI analysis.")
        
        # --- AI Analysis Step (unchanged but with better data) ---
        model = genai.GenerativeModel('gemini-2.5-flash')
        prompt = f"Act as a senior Quantitative Financial Analyst. Your user's goal is '{user_query}'. Analyze these stocks based on this high-quality data: {json.dumps(quant_profiles, indent=2)}. You MUST select the top 3-4 stocks and provide a data-driven reason citing at least two metrics from the data. Format as a valid JSON array of objects with keys: 'ticker', 'company_name', 'reason'."
        
        response = model.generate_content(prompt)
        cleaned_response = response.text.strip().replace('```json', '').replace('```', '').strip()
        
        try:
            return jsonify(json.loads(cleaned_response))
        except json.JSONDecodeError:
            return jsonify([{"ticker": "SYSTEM", "company_name": "AI Error", "reason": "The AI analysis module failed to return a valid response after processing the financial data."}])

    except Exception as e:
        print(f"FATAL ERROR in main process: {e}")
        return jsonify({"error": "A fatal internal server error occurred."}), 500

# get_stock_details endpoint remains the same, as it's a single, reliable call
@app.route('/api/get_stock_details/<string:ticker>')
def get_stock_details(ticker):
    try:
        profile_url = f"https://financialmodelingprep.com/api/v3/profile/{ticker}?apikey={FMP_API_KEY}"
        response = requests.get(profile_url, timeout=10)
        if response.status_code != 200 or not response.json():
            return jsonify({"error": "Could not retrieve FMP data."}), 404
        return jsonify(response.json()[0])
    except Exception as e:
        return jsonify({"error": f"An internal error occurred: {e}"}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)