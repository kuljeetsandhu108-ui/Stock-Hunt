# app.py (GeniusMind Quant Analyst - STABLE Version)

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


def get_intelligent_screener_params(query):
    """
    Analyzes the user's query to generate intelligent screening parameters for the FMP API.
    """
    params = {
        'marketCapMoreThan': 10000000000,
        'volumeMoreThan': 100000,
        'limit': 20 # Increased limit for a wider initial pool
    }
    if 'high return' in query or 'growth' in query:
        params['isActivelyTrading'] = True
    if 'less investment' in query or 'undervalued' in query:
        params['peRatioLessThan'] = 30 # Slightly increased PE for growth potential
        params['priceToSalesRatioLessThan'] = 4
    if 'safe' in query or 'stable' in query:
        params['betaLowerThan'] = 1.0
        params['dividendYieldMoreThan'] = 0.5 # Yield in percentage
    return params


# --- Flask Routes ---

@app.route('/')
def index():
    """Serves the main HTML page."""
    return render_template('index.html')

@app.route('/api/get_stock_recommendation', methods=['POST'])
def get_stock_recommendation():
    """
    The core endpoint for quantitative stock analysis and AI recommendation.
    """
    try:
        user_query = request.json.get('query', '').lower()
        if not user_query:
            return jsonify({"error": "Query not provided"}), 400

        # --- Step 1: Intelligent Stock Screening with FMP ---
        country = "IN" if "indian" in user_query else "US"
        screener_params = get_intelligent_screener_params(user_query)
        screener_url = f"https://financialmodelingprep.com/api/v3/stock-screener?country={country}&apikey={FMP_API_KEY}"
        for key, value in screener_params.items():
            screener_url += f"&{key}={value}"
            
        screener_response = requests.get(screener_url)
        if screener_response.status_code != 200 or not screener_response.json():
            return jsonify({"error": "Could not fetch a list of candidate stocks."}), 500
        
        candidate_stocks = [stock['symbol'] for stock in screener_response.json()]
        if not candidate_stocks:
            return jsonify({"error": "No stocks were found that match your initial screening criteria."}), 404

        # --- Step 2: Deep Data Aggregation for each Candidate ---
        quant_profiles = []
        for ticker in candidate_stocks[:15]: # Analyze top 15 candidates
            try:
                # --- ROBUST TICKER HANDLING ---
                # If ticker from FMP already contains a '.', use it directly (e.g., for .BO)
                # Otherwise, if it's an Indian stock, append .NS
                if '.' in ticker:
                    yf_ticker_str = ticker
                else:
                    yf_ticker_str = f"{ticker}.NS" if country == "IN" else ticker
                
                yf_data = yf.Ticker(yf_ticker_str)
                info = yf_data.info
                if not info or info.get('marketCap') is None:
                    print(f"Skipping {ticker} due to incomplete yfinance data.")
                    continue

                ratios_url = f"https://financialmodelingprep.com/api/v3/ratios-ttm/{ticker}?apikey={FMP_API_KEY}"
                ratios_response = requests.get(ratios_url)
                ratios = ratios_response.json()[0] if ratios_response.status_code == 200 and ratios_response.json() else {}

                profile = {
                    "ticker": ticker,
                    "companyName": info.get('longName'),
                    "sector": info.get('sector'),
                    "marketCap": info.get('marketCap'),
                    "peRatio": ratios.get('priceEarningsRatioTTM'),
                    "pegRatio": info.get('pegRatio'),
                    "priceToSalesRatio": ratios.get('priceToSalesRatioTTM'),
                    "returnOnEquity": ratios.get('returnOnEquityTTM'),
                    "debtToEquityRatio": ratios.get('debtToEquityRatioTTM'),
                    "profitMargin": info.get('profitMargins'),
                    "revenueGrowth": info.get('revenueGrowth')
                }
                quant_profiles.append(profile)
            except Exception as e:
                print(f"Could not process data for {ticker}: {e}")
                continue

        # --- Step 3: High-End AI Analysis with Gemini ---
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        # --- CRITICAL FIX APPLIED HERE ---
        # The placeholders {{pegRatio}} and {{returnOnEquity}} are now escaped with double braces
        # to prevent the Python f-string from trying to evaluate them as variables.
        prompt = f"""
        Act as a senior Quantitative Financial Analyst. Your task is to perform a deep analysis of the following stocks based on the provided quantitative data and the user's investment goal. Your reasoning must be sharp, data-driven, and based on established financial principles.

        **User's Investment Goal:** "{user_query}"

        **Quantitative Stock Profiles:**
        ```json
        {json.dumps(quant_profiles, indent=2)}
        ```

        **Your Task:**
        1.  **Analyze and Filter:** Scrutinize each stock's profile. Use indicators like P/E Ratio (for value), PEG Ratio (for growth at a reasonable price), Return on Equity (for profitability), and Debt-to-Equity Ratio (for financial health) to evaluate how well each stock aligns with the user's goal.
        2.  **Select Top 3-4 Stocks:** Choose the stocks that provide the most compelling, data-supported case.
        3.  **Provide Quantitative Reasoning:** For each selected stock, write a concise, expert reason. **You MUST cite at least two specific data points from their profile in your reason.** For example, "Recommended for its strong growth potential, evidenced by a low PEG ratio of {{pegRatio}} and high Return on Equity of {{returnOnEquity}}."
        4.  **Format the Output:** The final output MUST be a valid JSON array of objects. Do not include any text, explanation, or markdown formatting outside of the JSON structure. Each object must have the keys: "ticker", "company_name", and "reason".
        """
        
        response = model.generate_content(prompt)
        cleaned_response = response.text.strip().replace('```json', '').replace('```', '').strip()
        
        try:
            parsed_json = json.loads(cleaned_response)
            return jsonify(parsed_json)
        except json.JSONDecodeError:
            print(f"Critical Error: Gemini response was not valid JSON.\nResponse:\n{cleaned_response}")
            return jsonify({"error": "The AI analysis module failed to return a valid format."}), 500

    except Exception as e:
        print(f"A critical error occurred in the main process: {e}")
        return jsonify({"error": "An internal server error occurred."}), 500


@app.route('/api/get_stock_details/<string:ticker>')
def get_stock_details(ticker):
    """Fetches detailed profile data for a single stock ticker."""
    try:
        profile_url = f"https://financialmodelingprep.com/api/v3/profile/{ticker}?apikey={FMP_API_KEY}"
        profile_response = requests.get(profile_url)
        
        if profile_response.status_code != 200 or not profile_response.json():
            return jsonify({"error": "Could not retrieve FMP data for this stock."}), 404
        profile_data = profile_response.json()[0]
        
        combined_data = {
            "ticker": profile_data.get('symbol', ticker.upper()),
            "companyName": profile_data.get('companyName', 'N/A'),
            "sector": profile_data.get('sector', 'N/A'),
            "industry": profile_data.get('industry', 'N/A'),
            "website": profile_data.get('website', '#'),
            "description": profile_data.get('description', 'N/A'),
            "marketCap": profile_data.get('mktCap', 'N/A'),
        }
        return jsonify(combined_data)

    except Exception as e:
        print(f"An error occurred in get_stock_details: {e}")
        return jsonify({"error": "An internal error occurred."}), 500


# --- Main execution ---
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)