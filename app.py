import os
import time
import json
from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
from dotenv import load_dotenv
import google.generativeai as genai

# Load environment variables from .env file
load_dotenv()

# --- API CONFIGURATION ---
FMP_API_KEY = os.getenv('FMP_API_KEY')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

if not FMP_API_KEY or not GEMINI_API_KEY:
    raise ValueError("API keys for FMP and Gemini must be set in the .env file.")

# Configure the Gemini API
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.5-flash')

FMP_BASE_URL = "https://financialmodelingprep.com/api/v3"

# --- FLASK APP INITIALIZATION ---
app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

# --- HELPER FUNCTIONS (SCREENER) ---

def get_symbols_from_ai(query):
    """
    Uses Gemini AI to extract relevant stock symbols from a user's query.
    """
    prompt = f"""
    Analyze the following user request and identify the most relevant stock market ticker symbols.
    Return ONLY a raw Python list of strings in your response, with no other text, explanation, or formatting.
    For example: ["AAPL", "MSFT", "GOOGL"]
    If you cannot find any relevant tickers, return an empty list: []

    User Request: "{query}"
    """
    try:
        response = model.generate_content(prompt)
        cleaned_response = response.text.strip().replace("'", '"')
        symbols = json.loads(cleaned_response)
        print(f"AI identified symbols: {symbols}")
        return symbols
    except Exception as e:
        print(f"Error processing AI symbol extraction: {e}")
        if 'indian' in query.lower() or 'india' in query.lower():
            return ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS"]
        return []

def get_stock_data_with_ai_reason(symbol):
    """
    Fetches basic financial data and generates an investment thesis using Gemini AI.
    """
    try:
        quote_url = f"{FMP_BASE_URL}/quote/{symbol}?apikey={FMP_API_KEY}"
        quote_data = requests.get(quote_url).json()
        if not quote_data: return None

        financials = {
            "price": quote_data[0].get('price'),
            "companyName": quote_data[0].get('name'),
            "symbol": quote_data[0].get('symbol'),
            "description": f"A company in the {quote_data[0].get('exchange')} exchange.", # Placeholder description for speed
        }

        prompt = f"""
        Act as a professional financial analyst. Based on the company name {financials['companyName']} ({financials['symbol']}), provide a concise, compelling, and valid investment thesis (a "reason") for why this stock might give high returns in the next 5 years.
        The reason should be a single, fluent sentence.
        """
        response = model.generate_content(prompt)
        financials['reason'] = response.text.strip()
        
        return financials
    except Exception as e:
        print(f"Error fetching or processing data for {symbol}: {e}")
        return None

# --- HELPER FUNCTION (DETAILED VIEW) --- NEW!

def get_stock_details(symbol):
    """
    Fetches a comprehensive set of details for a single stock symbol.
    """
    try:
        profile_url = f"{FMP_BASE_URL}/profile/{symbol}?apikey={FMP_API_KEY}"
        profile_data = requests.get(profile_url).json()

        quote_url = f"{FMP_BASE_URL}/quote/{symbol}?apikey={FMP_API_KEY}"
        quote_data = requests.get(quote_url).json()

        if not profile_data or not quote_data:
            return None

        # Consolidate all the rich data into one dictionary
        details = {
            "symbol": profile_data[0].get('symbol'),
            "companyName": profile_data[0].get('companyName'),
            "price": profile_data[0].get('price'),
            "image": profile_data[0].get('image'),
            "exchange": profile_data[0].get('exchangeShortName'),
            "industry": profile_data[0].get('industry'),
            "sector": profile_data[0].get('sector'),
            "description": profile_data[0].get('description'),
            "mktCap": quote_data[0].get('marketCap'),
            "dayHigh": quote_data[0].get('dayHigh'),
            "dayLow": quote_data[0].get('dayLow'),
            "yearHigh": quote_data[0].get('yearHigh'),
            "yearLow": quote_data[0].get('yearLow'),
            "volume": quote_data[0].get('volume'),
            "avgVolume": quote_data[0].get('avgVolume'),
        }
        return details
    except Exception as e:
        print(f"Error fetching detailed data for {symbol}: {e}")
        return None

# --- API ENDPOINTS ---

@app.route('/api/screen', methods=['POST'])
def screen_stocks():
    """
    The main API endpoint that orchestrates the AI and data fetching for the initial list.
    """
    data = request.get_json()
    if not data or 'query' not in data:
        return jsonify({"error": "Invalid request. 'query' is required."}), 400

    query = data['query']
    print(f"Received query: '{query}'")

    target_symbols = get_symbols_from_ai(query)
    
    if not target_symbols:
        return jsonify({
            "response": "I couldn't identify any specific stocks from your request. Could you please be more precise?",
            "stocks": []
        })

    final_stock_list = []
    for symbol in target_symbols:
        stock_details = get_stock_data_with_ai_reason(symbol)
        if stock_details:
            final_stock_list.append(stock_details)
    
    summary_prompt = f"Based on the user's request '{query}', I have identified and analyzed several stocks. Briefly summarize this action in a confident, professional, and friendly tone."
    summary_response = model.generate_content(summary_prompt)

    response_data = {
        "response": summary_response.text.strip(),
        "stocks": final_stock_list
    }
    return jsonify(response_data)

@app.route('/api/stock_details/<symbol>', methods=['GET']) # NEW!
def stock_details(symbol):
    """
    Provides detailed information for a specific stock symbol.
    """
    print(f"Fetching detailed data for symbol: {symbol}")
    details = get_stock_details(symbol)
    if details:
        return jsonify(details)
    else:
        return jsonify({"error": "Could not retrieve details for the specified stock."}), 404

# --- RUN THE APP ---
if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=True)