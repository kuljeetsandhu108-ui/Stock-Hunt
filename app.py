# app.py (GeniusMind FINAL v2 - with JSON Extraction)

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

# --- NEW: Surgical JSON Extraction Function ---
def extract_json_from_string(text):
    """
    Finds and extracts the first valid JSON array (starting with '[' and ending with ']')
    from a larger string, ignoring any text before or after it.
    """
    try:
        # Find the starting position of the JSON array
        start_index = text.find('[')
        # Find the last closing bracket of the JSON array
        end_index = text.rfind(']')
        
        if start_index != -1 and end_index != -1 and end_index > start_index:
            # Slice the string to get only the JSON part
            json_str = text[start_index : end_index + 1]
            # Parse it to confirm it's valid JSON
            return json.loads(json_str)
        else:
            return None # Return None if no valid array is found
    except (json.JSONDecodeError, TypeError):
        return None


# --- Robust API Call Function ---
def make_fmp_request(url):
    """Makes a request to the FMP API with error handling."""
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
    print("\n--- NEW REQUEST RECEIVED ---")
    try:
        user_query = request.json.get('query', '').lower()
        country = "IN" if "indian" in user_query else "US"
        print(f"Step 1: Screening. Country: {country}, Query: '{user_query}'")

        base_url = f"https://financialmodelingprep.com/api/v3/stock-screener?country={country}&apikey={FMP_API_KEY}"
        price_match = re.search(r'(under|less than|below|upto)\s*(\d+)', user_query)
        if price_match: base_url += f"&priceLowerThan={price_match.group(2)}"
        if "growth" in user_query: base_url += "&revenueGrowthMoreThan=0.05"
        if "undervalued" in user_query: base_url += "&peRatioLessThan=25"
        screener_url = f"{base_url}&volumeMoreThan=50000&limit=40"
        
        candidate_list = make_fmp_request(screener_url)
        if not candidate_list:
            return jsonify([{"ticker": "SYSTEM", "company_name": "No Stocks Found", "reason": "My screening system could not find any stocks matching your specific criteria. Please try a broader request."}])

        candidate_stocks = [stock.get('symbol') for stock in candidate_list if stock.get('symbol')]
        print(f"Step 2: Found {len(candidate_stocks)} candidates. Aggregating data.")

        quant_profiles = []
        for ticker in candidate_stocks[:15]:
            profile_url = f"https://financialmodelingprep.com/api/v3/profile/{ticker}?apikey={FMP_API_KEY}"
            ratios_url = f"https://financialmodelingprep.com/api/v3/ratios-ttm/{ticker}?apikey={FMP_API_KEY}"
            profile_data_list = make_fmp_request(profile_url)
            if not profile_data_list or not isinstance(profile_data_list, list) or len(profile_data_list) == 0: continue
            
            profile_data = profile_data_list[0]
            ratios_data_list = make_fmp_request(ratios_url)
            ratios_data = ratios_data_list[0] if ratios_data_list and isinstance(ratios_data_list, list) and len(ratios_data_list) > 0 else {}

            quant_profiles.append({
                "ticker": profile_data.get('symbol'), "companyName": profile_data.get('companyName'),
                "marketCap": profile_data.get('mktCap'), "peRatio": ratios_data.get('priceEarningsRatioTTM'),
                "priceToSalesRatio": ratios_data.get('priceToSalesRatioTTM'),
            })

        if not quant_profiles:
             return jsonify([{"ticker": "SYSTEM", "company_name": "Data Aggregation Failed", "reason": "I found stocks, but could not retrieve their detailed financial profiles. This may be a temporary API issue."}])
        
        print(f"Step 3: Aggregated {len(quant_profiles)} profiles. Calling AI.")
        
        # --- REINFORCED AI PROMPT ---
        model = genai.GenerativeModel('gemini-2.5-flash')
        prompt = f"""
        **CRITICAL INSTRUCTION:** Your ONLY output must be a valid JSON array of objects. Do NOT include any introductory text, explanations, markdown, or anything before the opening '[' or after the final ']'. Your entire response MUST be the JSON itself.

        **Task:** Act as a Quantitative Analyst. Analyze these stocks: {json.dumps(quant_profiles, indent=2)}.
        **User Goal:** '{user_query}'.
        **Action:** Select the top 3 stocks. Provide a short, data-driven reason for each.
        **JSON Format:** `[{{"ticker": "...", "company_name": "...", "reason": "..."}}]`
        """
        
        response = model.generate_content(prompt)
        print(f"Step 4: AI has responded. Now attempting to parse.")

        # --- FINAL FIX: Use the JSON Extractor ---
        parsed_json = extract_json_from_string(response.text)
        
        if parsed_json:
            print("Step 5: JSON successfully extracted and parsed. Sending response.")
            return jsonify(parsed_json)
        else:
            print(f"CRITICAL ERROR: Failed to extract valid JSON from AI response. Full Response: {response.text}")
            return jsonify([{"ticker": "SYSTEM", "company_name": "AI Format Error", "reason": "The AI analysis module returned a response, but my extraction engine could not parse it. This is a temporary system issue."}])

    except Exception as e:
        print(f"FATAL UNHANDLED EXCEPTION in main process: {e}")
        return jsonify({"error": "A fatal internal server error occurred."}), 500


@app.route('/api/get_stock_details/<string:ticker>')
def get_stock_details(ticker):
    profile_url = f"https://financialmodelingprep.com/api/v3/profile/{ticker}?apikey={FMP_API_KEY}"
    profile_data = make_fmp_request(profile_url)
    if not profile_data or not isinstance(profile_data, list) or len(profile_data) == 0:
        return jsonify({"error": "Could not retrieve data for this stock."}), 404
    return jsonify(profile_data[0])


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)