document.addEventListener('DOMContentLoaded', () => {
    const userInput = document.getElementById('user-input');
    const sendBtn = document.getElementById('send-btn');
    const chatBox = document.getElementById('chat-box');
    const resultsContainer = document.getElementById('results-container');
    
    // Variable to store the last list of stocks for the "Back" button
    let lastStockResults = [];

    const addMessage = (message, sender) => {
        const messageElement = document.createElement('div');
        messageElement.classList.add('chat-message', `${sender}-message`);
        const textElement = document.createElement('p');
        textElement.textContent = message;
        messageElement.appendChild(textElement);
        chatBox.appendChild(messageElement);
        chatBox.scrollTop = chatBox.scrollHeight;
    };

    const showProcessing = (container) => {
        container.innerHTML = `
            <div class="processing-results">
                <div class="dot-flashing"></div>
                <p>Fetching Data...</p>
            </div>
        `;
    };

    const removeProcessingAnimation = () => {
        const processingElement = document.querySelector('.processing');
        if (processingElement) chatBox.removeChild(processingElement);
    };
    
    const handleSendMessage = async () => {
        const query = userInput.value.trim();
        if (query === '') return;

        addMessage(query, 'user');
        userInput.value = '';

        // Add the bot's "thinking" message directly
        const thinkingMessage = document.createElement('div');
        thinkingMessage.classList.add('chat-message', 'bot-message', 'processing');
        thinkingMessage.innerHTML = `<p>Analyzing data...</p><div class="dot-flashing"></div>`;
        chatBox.appendChild(thinkingMessage);
        chatBox.scrollTop = chatBox.scrollHeight;
        
        showProcessing(resultsContainer);

        try {
            const response = await fetch('http://127.0.0.1:5000/api/screen', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query: query }),
            });

            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
            const data = await response.json();
            
            removeProcessingAnimation();

            if (data.response) addMessage(data.response, 'bot');
            
            if (data.stocks && data.stocks.length > 0) {
                lastStockResults = data.stocks; // Save results
                renderStockList(lastStockResults);
            } else {
                resultsContainer.innerHTML = '<p class="error-message">No stocks found matching your criteria.</p>';
            }

        } catch (error) {
            console.error('Error fetching data:', error);
            removeProcessingAnimation();
            addMessage('Sorry, something went wrong. Please check the console.', 'bot');
            resultsContainer.innerHTML = `<p class="error-message">Error: ${error.message}. Is the backend server running?</p>`;
        }
    };
    
    // Renders the initial list of stocks
    const renderStockList = (stocks) => {
        let content = '<h2>Recommended Stocks</h2>';
        content += '<table class="stock-table"><thead><tr><th>Symbol</th><th>Company</th><th>Price</th><th>Reason</th></tr></thead><tbody>';
        stocks.forEach(stock => {
            content += `
                <tr class="stock-item" data-symbol="${stock.symbol}">
                    <td>${stock.symbol}</td>
                    <td>${stock.companyName}</td>
                    <td>$${stock.price ? stock.price.toFixed(2) : 'N/A'}</td>
                    <td>${stock.reason}</td>
                </tr>
            `;
        });
        content += '</tbody></table>';
        resultsContainer.innerHTML = content;

        document.querySelectorAll('.stock-item').forEach(item => {
            item.addEventListener('click', () => {
                const symbol = item.dataset.symbol;
                fetchAndRenderStockDetails(symbol);
            });
        });
    };

    // Fetches and renders the detailed view for a single stock
    const fetchAndRenderStockDetails = async (symbol) => {
        showProcessing(resultsContainer);
        try {
            const response = await fetch(`http://127.0.0.1:5000/api/stock_details/${symbol}`);
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
            const data = await response.json();
            renderDetailedView(data);
        } catch (error) {
            console.error('Error fetching stock details:', error);
            resultsContainer.innerHTML = `<p class="error-message">Error: Could not fetch details for ${symbol}.</p>`;
        }
    };

    // Renders the beautiful detailed view
    const renderDetailedView = (data) => {
        const formatMarketCap = (num) => {
            if (num > 1_000_000_000_000) return `${(num / 1_000_000_000_000).toFixed(2)} T`;
            if (num > 1_000_000_000) return `${(num / 1_000_000_000).toFixed(2)} B`;
            if (num > 1_000_000) return `${(num / 1_000_000).toFixed(2)} M`;
            return num;
        };
        
        let content = `
            <div class="stock-detail-view">
                <button class="back-button">&larr; Back to List</button>
                <div class="stock-detail-header">
                    <img src="${data.image}" alt="${data.companyName} logo" class="company-logo">
                    <div>
                        <h2>${data.companyName} (${data.symbol})</h2>
                        <p class="exchange">${data.exchange} | ${data.sector}</p>
                    </div>
                </div>
                <div class="stock-price-main">$${data.price ? data.price.toFixed(2) : 'N/A'}</div>
                <div class="stock-detail-metrics">
                    <div class="metric-item"><span>Day High</span><span>$${data.dayHigh.toFixed(2)}</span></div>
                    <div class="metric-item"><span>Day Low</span><span>$${data.dayLow.toFixed(2)}</span></div>
                    <div class="metric-item"><span>Year High</span><span>$${data.yearHigh.toFixed(2)}</span></div>
                    <div class="metric-item"><span>Year Low</span><span>$${data.yearLow.toFixed(2)}</span></div>
                    <div class="metric-item"><span>Market Cap</span><span>${formatMarketCap(data.mktCap)}</span></div>
                    <div class="metric-item"><span>Volume</span><span>${data.volume.toLocaleString()}</span></div>
                </div>
                <h3>About ${data.companyName}</h3>
                <p class="company-description">${data.description}</p>
            </div>
        `;
        resultsContainer.innerHTML = content;

        // Add event listener to the new back button
        document.querySelector('.back-button').addEventListener('click', () => {
            renderStockList(lastStockResults); // Re-render the saved list
        });
    };

    sendBtn.addEventListener('click', handleSendMessage);
    userInput.addEventListener('keypress', (event) => {
        if (event.key === 'Enter') handleSendMessage();
    });

    addMessage("Hello! I am your AI Stock Screener. How can I help you find your next investment?", 'bot');
});