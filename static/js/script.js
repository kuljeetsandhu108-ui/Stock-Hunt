/* /static/js/script.js (v2 Animated Intelligence Engine) */

document.addEventListener('DOMContentLoaded', () => {
    // --- DOM Element Selection (Chat) ---
    const chatWindow = document.getElementById('chat-window');
    const userInput = document.getElementById('user-input');
    const sendBtn = document.getElementById('send-btn');
    const loadingIndicator = document.getElementById('loading-indicator');

    // --- DOM Element Selection (V2 Modal Dashboard) ---
    const stockModal = document.getElementById('stock-modal');
    const modalCloseBtn = document.querySelector('.close-button');
    // Header
    const modalCompanyName = document.getElementById('modal-company-name');
    const modalSectorIndustry = document.getElementById('modal-sector-industry');
    // Live Data
    const modalLivePrice = document.getElementById('modal-live-price');
    const modalPriceChange = document.getElementById('modal-price-change');
    // Quote Grid
    const modalDayLow = document.getElementById('modal-day-low');
    const modalDayHigh = document.getElementById('modal-day-high');
    const modalYearLow = document.getElementById('modal-year-low');
    const modalYearHigh = document.getElementById('modal-year-high');
    const modalMarketCap = document.getElementById('modal-market-cap');
    const modalVolume = document.getElementById('modal-volume');
    // Profile
    const modalDescription = document.getElementById('modal-description');
    const modalWebsite = document.getElementById('modal-website');
    // Tables & Gauges
    const fundamentalsTable = document.getElementById('fundamentals-table');
    const rsiGaugeFill = document.getElementById('rsi-gauge-fill');
    const rsiGaugeValue = document.getElementById('rsi-gauge-value');
    const smaIndicatorValue = document.getElementById('sma-indicator-value');
    const smaIndicatorText = document.getElementById('sma-indicator-text');
    
    // --- Global State ---
    let priceUpdateInterval; // Holds the interval for the live price ticker

    // --- Core Event Listeners ---
    sendBtn.addEventListener('click', handleUserQuery);
    userInput.addEventListener('keydown', (event) => {
        if (event.key === 'Enter' && !event.shiftKey) {
            event.preventDefault();
            handleUserQuery();
        }
    });

    modalCloseBtn.addEventListener('click', closeModal);
    window.addEventListener('click', (event) => {
        if (event.target == stockModal) closeModal();
    });
    
    chatWindow.addEventListener('click', handleStockCardClick);

    // ===================================
    // ===== CHAT ENGINE FUNCTIONS =====
    // ===================================

    async function handleUserQuery() {
        const query = userInput.value.trim();
        if (!query) return;
        displayUserMessage(query);
        userInput.value = '';
        userInput.disabled = true;
        sendBtn.disabled = true;
        loadingIndicator.style.display = 'block';

        try {
            const response = await fetch('/api/get_stock_recommendation', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query: query }),
            });
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
            const data = await response.json();
            const resultsHTML = createResultsDisplay(data);
            displayBotMessage("Here are my findings. Click on any stock for a detailed view.", resultsHTML);
        } catch (error) {
            console.error("Error in handleUserQuery:", error);
            displayBotMessage(`<p>I'm sorry, a critical error occurred. Please try again.</p>`);
        } finally {
            loadingIndicator.style.display = 'none';
            userInput.disabled = false;
            sendBtn.disabled = false;
            userInput.focus();
        }
    }

    function displayUserMessage(message) {
        const messageElement = document.createElement('div');
        messageElement.className = 'chat-message user-message';
        messageElement.innerHTML = `<p class="message-text">${message}</p>`;
        chatWindow.appendChild(messageElement);
        scrollToBottom();
    }

    function displayBotMessage(text, htmlContent = '') {
        const messageElement = document.createElement('div');
        messageElement.className = 'chat-message bot-message';
        messageElement.innerHTML = `<p class="message-text">${text}</p>${htmlContent}`;
        chatWindow.appendChild(messageElement);
        scrollToBottom();
    }
    
    function createResultsDisplay(data) {
        if (!data || data.length === 0) return "<p>No suitable stocks were found.</p>";
        if (data[0].ticker === "SYSTEM") {
            const systemMessage = data[0];
            return `<div class="system-card"><div class="card-header"><h3 class="ticker-symbol">System Message</h3><p class="company-name">${systemMessage.company_name}</p></div><div class="card-body"><p class="reason">${systemMessage.reason}</p></div></div>`;
        }
        let cardsHTML = '<div class="results-grid">';
        data.forEach(stock => {
            cardsHTML += `<div class="stock-card" data-ticker="${stock.ticker}"><div class="card-header"><h3 class="ticker-symbol">${stock.ticker}</h3><p class="company-name">${stock.company_name || 'N/A'}</p></div><div class="card-body"><p class="reason">${stock.reason}</p></div></div>`;
        });
        cardsHTML += '</div>';
        return cardsHTML;
    }

    function scrollToBottom() {
        chatWindow.scrollTop = chatWindow.scrollHeight;
    }

    // =========================================
    // ===== V2 DASHBOARD ENGINE FUNCTIONS =====
    // =========================================

    async function handleStockCardClick(event) {
        const card = event.target.closest('.stock-card');
        if (!card || !card.dataset.ticker || card.dataset.ticker === "SYSTEM") return;
        const ticker = card.dataset.ticker;
        
        // Show modal with loading state
        stockModal.style.display = 'block';
        resetModalToLoadingState();
        
        try {
            const response = await fetch(`/api/get_stock_dashboard/${ticker}`);
            if (!response.ok) { throw new Error('Failed to fetch dashboard data.'); }
            const data = await response.json();
            populateDashboard(data);
        } catch (error) {
            console.error('Error fetching dashboard data:', error);
            modalCompanyName.innerText = "Error Loading Data";
        }
    }
    
    function populateDashboard(data) {
        // --- Header ---
        modalCompanyName.innerText = `${data.profile.companyName} (${data.profile.symbol})`;
        modalSectorIndustry.innerText = `${data.profile.sector || 'N/A'} / ${data.profile.industry || 'N/A'}`;

        // --- Live Quote ---
        const price = data.liveQuote.price;
        const change = data.liveQuote.change;
        const changesPercentage = data.liveQuote.changesPercentage;
        
        modalLivePrice.innerText = formatNumber(price, 2);
        modalPriceChange.innerText = `${change > 0 ? '+' : ''}${formatNumber(change, 2)} (${formatNumber(changesPercentage, 2)}%)`;
        modalPriceChange.className = `price-change ${change >= 0 ? 'up' : 'down'}`;

        // Start the live price "ticker" simulation
        startPriceTicker(price);

        // --- Quote Grid ---
        modalDayLow.innerText = formatNumber(data.liveQuote.dayLow);
        modalDayHigh.innerText = formatNumber(data.liveQuote.dayHigh);
        modalYearLow.innerText = formatNumber(data.liveQuote.yearLow);
        modalYearHigh.innerText = formatNumber(data.liveQuote.yearHigh);
        modalMarketCap.innerText = formatLargeNumber(data.liveQuote.marketCap);
        modalVolume.innerText = formatLargeNumber(data.liveQuote.volume);
        
        // --- Profile ---
        modalDescription.innerText = data.profile.description || "No company description available.";
        modalWebsite.href = data.profile.website || '#';

        // --- Fundamentals Table ---
        const fundamentals = data.fundamentals;
        fundamentalsTable.innerHTML = `
            <tr><td>P/E Ratio</td><td>${formatNumber(fundamentals.peRatio)}</td></tr>
            <tr><td>Price to Sales</td><td>${formatNumber(fundamentals.priceToSalesRatio)}</td></tr>
            <tr><td>Price to Book</td><td>${formatNumber(fundamentals.priceToBookRatio)}</td></tr>
            <tr><td>Return on Equity (ROE)</td><td>${formatAsPercentage(fundamentals.returnOnEquity)}</td></tr>
            <tr><td>Dividend Yield</td><td>${formatAsPercentage(fundamentals.dividendYield)}</td></tr>
            <tr><td>Debt to Equity</td><td>${formatNumber(fundamentals.debtToEquity)}</td></tr>
        `;
        
        // --- Technicals ---
        updateRsiGauge(data.technicals.rsi);
        updateSmaIndicator(price, data.technicals.sma);
    }
    
    function updateRsiGauge(rsi) {
        if (rsi === null || rsi === undefined) {
            rsiGaugeValue.innerText = "N/A";
            setGaugeRotation(rsiGaugeFill, 0); // No rotation
            return;
        }
        rsiGaugeValue.innerText = formatNumber(rsi, 2);
        // Convert RSI (0-100) to a rotation angle (0 to 180 degrees or 0 to 0.5 turn)
        const rotation = rsi / 100 * 0.5;
        setGaugeRotation(rsiGaugeFill, rotation);
    }
    
    function updateSmaIndicator(price, sma) {
        if (price === null || sma === null || price === undefined || sma === undefined) {
            smaIndicatorValue.className = "indicator-value neutral";
            smaIndicatorValue.innerText = "N/A";
            smaIndicatorText.innerText = "Data unavailable";
            return;
        }
        if (price > sma) {
            smaIndicatorValue.className = "indicator-value up";
            smaIndicatorValue.innerText = "Bullish";
            smaIndicatorText.innerText = `Price (${formatNumber(price, 2)}) is above the 50-day SMA (${formatNumber(sma, 2)})`;
        } else {
            smaIndicatorValue.className = "indicator-value down";
            smaIndicatorValue.innerText = "Bearish";
            smaIndicatorText.innerText = `Price (${formatNumber(price, 2)}) is below the 50-day SMA (${formatNumber(sma, 2)})`;
        }
    }

    function setGaugeRotation(element, value) {
        // value is a float between 0 and 0.5 (for a half-circle)
        element.style.transform = `rotate(${value}turn)`;
    }

    function startPriceTicker(initialPrice) {
        clearInterval(priceUpdateInterval); // Clear any previous ticker
        let currentPrice = initialPrice;
        priceUpdateInterval = setInterval(() => {
            // Simulate a small price fluctuation
            const fluctuation = (Math.random() - 0.5) * (currentPrice * 0.0005);
            currentPrice += fluctuation;
            modalLivePrice.innerText = formatNumber(currentPrice, 2);
        }, 1500); // Update every 1.5 seconds
    }
    
    function closeModal() {
        stockModal.style.display = 'none';
        clearInterval(priceUpdateInterval); // CRITICAL: Stop the ticker when closing modal
    }
    
    function resetModalToLoadingState() {
        // Reset all fields to a loading state to prevent showing old data
        modalCompanyName.innerText = "Loading Dashboard...";
        modalSectorIndustry.innerText = "Fetching data...";
        modalLivePrice.innerText = "--";
        modalPriceChange.innerText = "--";
        modalPriceChange.className = "price-change";
        const loadingText = "--";
        modalDayLow.innerText = loadingText;
        modalDayHigh.innerText = loadingText;
        modalYearLow.innerText = loadingText;
        modalYearHigh.innerText = loadingText;
        modalMarketCap.innerText = loadingText;
        modalVolume.innerText = loadingText;
        modalDescription.innerText = "";
        modalWebsite.href = "#";
        fundamentalsTable.innerHTML = "";
        rsiGaugeValue.innerText = "--";
        setGaugeRotation(rsiGaugeFill, 0);
        smaIndicatorValue.className = "indicator-value neutral";
        smaIndicatorValue.innerText = "--";
        smaIndicatorText.innerText = "";
    }
    
    // --- UTILITY FUNCTIONS ---
    function formatNumber(num, decimals = 2) {
        if (num === null || num === undefined) return "N/A";
        return num.toFixed(decimals);
    }
    
    function formatLargeNumber(num) {
        if (num === null || num === undefined) return "N/A";
        if (num >= 1e12) return (num / 1e12).toFixed(2) + 'T'; // Trillion
        if (num >= 1e9) return (num / 1e9).toFixed(2) + 'B'; // Billion
        if (num >= 1e6) return (num / 1e6).toFixed(2) + 'M'; // Million
        return num.toLocaleString();
    }
    
    function formatAsPercentage(num) {
        if (num === null || num === undefined) return "N/A";
        return (num * 100).toFixed(2) + '%';
    }
});