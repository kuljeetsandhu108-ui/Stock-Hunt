# app.py (GeniusMind v2 - Dashboard Powerhouse)

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
try:
    genai.configure(api_key=GEMINI_API_KEY)
except Exception as e:
    print(f"CRITICAL STARTUP ERROR: Could not configure Gemini AI. Error: {e}")

# --- Robust API Call Function ---
def make_fmp_request(url):
    """Makes a request to the FMP API with robust error handling."""
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as req_err:
        print(f"FMP request error: {req_err}")
    return None

# --- Main Logic ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/get_stock_recommendation', methods=['POST'])
def get_stock_recommendation():
    # This core recommendation engine is stable and will remain.
    # [The code from the previous working version is assumed here for brevity]
    # In a real file, the full, working get_stock_recommendation function would be here.
    # For this upgrade, we are focusing on the *new* dashboard endpoint.
    # Let's paste the working logic back in to be safe.
    print("\n--- NEW RECOMMENDATION REQUEST RECEIVED ---")
    try:
        user_query = request.json.get('query', '').lower()
        country = "IN" if "indian" in user_query else "US"
        base_url = f"https://financialmodelingprep.com/api/v3/stock-screener?country={country}&apikey={FMP_API_KEY}"
        price_match = re.search(r'(under|less than|below|upto)\s*(\d+)', user_query)
        if price_match: base_url += f"&priceLowerThan={price_match.group(2)}"
        screener_url = f"{base_url}&volumeMoreThan=50000&limit=40"
        candidate_list = make_fmp_request(screener_url)
        if not candidate_list:
            return jsonify([{"ticker": "SYSTEM", "company_name": "No Stocks Found", "reason": "My screening system could not find any stocks matching your specific criteria."}])
        candidate_stocks = [stock.get('symbol') for stock in candidate_list if stock.get('symbol')]
        quant_profiles = []
        for ticker in candidate_stocks[:15]:
            profile_url = f"https://financialmodelingprep.com/api/v3/profile/{ticker}?apikey={FMP_API_KEY}"
            profile_data_list = make_fmp_request(profile_url)
            if not profile_data_list or len(profile_data_list) == 0: continue
            quant_profiles.append({"ticker": profile_data_list[0].get('symbol'), "companyName": profile_data_list[0].get('companyName')})
        if not quant_profiles:
             return jsonify([{"ticker": "SYSTEM", "company_name": "Data Aggregation Failed", "reason": "Could not retrieve profiles for the found stocks."}])
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = f"**CRITICAL INSTRUCTION:** Your ONLY output must be a valid JSON array of objects. Do NOT include any text before the opening '[' or after the final ']'.\n**Task:** Analyze these stocks: {json.dumps(quant_profiles)} for a user whose goal is '{user_query}'. Select the top 3 and give a short, data-driven reason. \n**JSON Format:** `[{{\"ticker\": \"...\", \"company_name\": \"...\", \"reason\": \"...\"}}]`"
        response = model.generate_content(prompt)
        start_index = response.text.find('[')
        end_index = response.text.rfind(']')
        if start_index != -1 and end_index != -1:
            json_str = response.text[start_index : end_index + 1]
            return jsonify(json.loads(json_str))
        else:
            return jsonify([{"ticker": "SYSTEM", "company_name": "AI Format Error", "reason": "The AI analysis module returned an invalid format."}])
    except Exception as e:
        print(f"FATAL ERROR in recommendation: {e}")
        return jsonify({"error": "A fatal internal server error occurred."}), 500


# --- NEW DASHBOARD DATA ENDPOINT ---
@app.route('/api/get_stock_dashboard/<string:ticker>')
def get_stock_dashboard(ticker):
    """
    This single, powerful endpoint gathers all data needed for the detailed dashboard view.
    """
    print(f"\n--- GATHERING DASHBOARD DATA FOR {ticker} ---")
    try:
        # 1. Company Profile and Live Price (Quote)
        profile_data = make_fmp_request(f"https://financialmodelingprep.com/api/v3/profile/{ticker}?apikey={FMP_API_KEY}")
        quote_data = make_fmp_request(f"https://financialmodelingprep.com/api/v3/quote/{ticker}?apikey={FMP_API_KEY}")
        
        # 2. Fundamental Data (Financial Ratios)
        ratios_data = make_fmp_request(f"https://financialmodelingprep.com/api/v3/ratios-ttm/{ticker}?apikey={FMP_API_KEY}")

        # 3. Technical Data (RSI and SMA) - Your paid plan is essential for this!
        rsi_data = make_fmp_request(f"https://financialmodelingprep.com/api/v4/technical_indicator/daily/{ticker}?period=14&type=rsi&apikey={FMP_API_KEY}")
        sma_data = make_fmp_request(f"https://financialmodelingprep.com/api/v4/technical_indicator/daily/{ticker}?period=50&type=sma&apikey={FMP_API_KEY}")

        # --- Defensive Data Handling ---
        # Ensure we have the most critical data before proceeding
        if not profile_data or not quote_data:
            return jsonify({"error": "Could not retrieve essential company data."}), 404
        
        # Aggregate all data into a single response object
        # Use .get() extensively to prevent errors if a key is missing
        profile = profile_data[0] if profile_data else {}
        quote = quote_data[0] if quote_data else {}
        ratios = ratios_data[0] if ratios_data else {}
        
        dashboard_data = {
            "profile": {
                "companyName": profile.get('companyName'),
                "symbol": profile.get('symbol'),
                "description": profile.get('description'),
                "website": profile.get('website'),
                "sector": profile.get('sector'),
                "industry": profile.get('industry')
            },
            "liveQuote": {
                "price": quote.get('price'),
                "change": quote.get('change'),
                "changesPercentage": quote.get('changesPercentage'),
                "dayLow": quote.get('dayLow'),
                "dayHigh": quote.get('dayHigh'),
                "yearHigh": quote.get('yearHigh'),
                "yearLow": quote.get('yearLow'),
                "marketCap": quote.get('marketCap'),
                "volume": quote.get('volume')
            },
            "fundamentals": {
                "peRatio": ratios.get('priceEarningsRatioTTM'),
                "priceToSalesRatio": ratios.get('priceToSalesRatioTTM'),
                "priceToBookRatio": ratios.get('priceToBookRatioTTM'),
                "returnOnEquity": ratios.get('returnOnEquityTTM'),
                "dividendYield": ratios.get('dividendYieldTTM'),
                "debtToEquity": ratios.get('debtToEquityRatioTTM')
            },
            "technicals": {
                "rsi": rsi_data[0].get('rsi') if rsi_data else None,
                "sma": sma_data[0].get('sma') if sma_data else None
            }
        }
        
        print(f"SUCCESS: Assembled full dashboard for {ticker}.")
        return jsonify(dashboard_data)

    except Exception as e:
        print(f"FATAL ERROR assembling dashboard for {ticker}: {e}")
        return jsonify({"error": "An internal server error occurred while building the dashboard."}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)