import os
import time
import json
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import requests
from dotenv import load_dotenv
import google.generativeai as genai

# Load environment variables from .env file for local development
load_dotenv()

# --- API CONFIGURATION ---
FMP_API_KEY = os.getenv('FMP_API_KEY')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

# This check provides a clear warning if keys are missing during startup.
if not FMP_API_KEY or not GEMINI_API_KEY:
    print("CRITICAL WARNING: FMP_API_KEY or GEMINI_API_KEY not found in environment variables.")
    print("Ensure your .env file is correct locally, or variables are set in Railway for deployment.")

# Configure the Gemini API, handling potential key issues gracefully
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-2.5-flash')
else:
    model = None # Set model to None if key is missing to prevent crashes

FMP_BASE_URL = "https://financialmodelingprep.com/api/v3"

# --- FLASK APP INITIALIZATION ---
# Flask will automatically find the 'static' and 'templates' folders.
app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})


# --- FRONTEND SERVING ROUTE ---
# This single, standard route will render our user interface.
@app.route('/')
def index():
    """Renders the index.html file from the 'templates' folder."""
    return render_template('index.html')


# --- API ENDPOINTS (Unchanged logic) ---
@app.route('/api/screen', methods=['POST'])
def screen_stocks():
    """Handles the user's initial query to find a list of stocks."""
    if not model:
        return jsonify({"error": "AI model is not configured due to missing API key."}), 500
        
    data = request.get_json()
    if not data or 'query' not in data:
        return jsonify({"error": "Invalid request. 'query' is required."}), 400

    query = data['query']
    print(f"Received screening query: '{query}'")
    
    target_symbols = get_symbols_from_ai(query)
    if not target_symbols:
        return jsonify({"response": "I couldn't identify any specific stocks from your request. Could you please be more precise?", "stocks": []})

    final_stock_list = []
    for symbol in target_symbols:
        details = get_stock_data_with_ai_reason(symbol)
        if details:
            final_stock_list.append(details)
    
    summary_prompt = f"Based on the user's request '{query}', I have identified and analyzed several stocks. Briefly summarize this action in a confident, professional, and friendly tone."
    summary_response = model.generate_content(summary_prompt)
    return jsonify({"response": summary_response.text.strip(), "stocks": final_stock_list})

@app.route('/api/stock_details/<symbol>', methods=['GET'])
def stock_details(symbol):
    """Provides detailed financial data for a single, specific stock symbol."""
    print(f"Fetching detailed data for symbol: {symbol}")
    details = get_stock_details(symbol)
    if details:
        return jsonify(details)
    else:
        return jsonify({"error": "Could not retrieve details for the specified stock."}), 404


# --- HELPER FUNCTIONS (Unchanged logic) ---
def get_symbols_from_ai(query):
    if not model: return [] 
    prompt = f'Analyze the following user request and identify relevant stock tickers. Return ONLY a Python list of strings. Example: ["AAPL", "MSFT"]\n\nRequest: "{query}"'
    try:
        response = model.generate_content(prompt)
        cleaned_response = response.text.strip().replace("'", '"')
        symbols = json.loads(cleaned_response)
        print(f"AI identified symbols: {symbols}")
        return symbols
    except Exception as e:
        print(f"Error processing AI symbol extraction: {e}")
        return []

def get_stock_data_with_ai_reason(symbol):
    if not FMP_API_KEY: return None
    try:
        quote_url = f"{FMP_BASE_URL}/quote/{symbol}?apikey={FMP_API_KEY}"
        quote_data = requests.get(quote_url).json()
        if not quote_data: return None
        financials = {"price": quote_data[0].get('price'), "companyName": quote_data[0].get('name'), "symbol": quote_data[0].get('symbol')}
        if not model:
            financials['reason'] = "AI reason generation is currently unavailable."
        else:
            prompt = f"For {financials['companyName']} ({financials['symbol']}), provide a single, compelling sentence explaining why it could be a strong long-term investment."
            response = model.generate_content(prompt)
            financials['reason'] = response.text.strip()
        return financials
    except Exception as e:
        print(f"Error getting basic data for {symbol}: {e}")
        return None

def get_stock_details(symbol):
    if not FMP_API_KEY: return None
    try:
        profile_url = f"{FMP_BASE_URL}/profile/{symbol}?apikey={FMP_API_KEY}"
        quote_url = f"{FMP_BASE_URL}/quote/{symbol}?apikey={FMP_API_KEY}"
        profile_data = requests.get(profile_url).json()[0]
        quote_data = requests.get(quote_url).json()[0]
        return {
            "symbol": profile_data.get('symbol'), "companyName": profile_data.get('companyName'),
            "price": profile_data.get('price'), "image": profile_data.get('image'),
            "exchange": profile_data.get('exchangeShortName'), "industry": profile_data.get('industry'),
            "sector": profile_data.get('sector'),
            "description": profile_data.get('description'),
            "mktCap": quote_data.get('marketCap'), "dayHigh": quote_data.get('dayHigh'),
            "dayLow": quote_data.get('dayLow'), "yearHigh": quote_data.get('yearHigh'),
            "yearLow": quote_data.get('yearLow'), "volume": quote_data.get('volume'),
            "avgVolume": quote_data.get('avgVolume')
        }
    except Exception as e:
        print(f"Error getting detailed data for {symbol}: {e}")
        return None


# --- RUN THE APP ---
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port)