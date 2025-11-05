/* /static/js/script.js (Production Hardening v2) */

document.addEventListener('DOMContentLoaded', () => {

    const chatWindow = document.getElementById('chat-window');
    const userInput = document.getElementById('user-input');
    const sendBtn = document.getElementById('send-btn');
    const loadingIndicator = document.getElementById('loading-indicator');
    const stockModal = document.getElementById('stock-modal');
    const modalCloseBtn = document.querySelector('.close-button');
    const modalBody = document.getElementById('modal-body');

    sendBtn.addEventListener('click', handleUserQuery);
    userInput.addEventListener('keydown', (event) => {
        if (event.key === 'Enter' && !event.shiftKey) {
            event.preventDefault();
            handleUserQuery();
        }
    });

    modalCloseBtn.addEventListener('click', () => { stockModal.style.display = 'none'; });
    window.addEventListener('click', (event) => {
        if (event.target == stockModal) stockModal.style.display = 'none';
    });
    
    chatWindow.addEventListener('click', handleStockCardClick);

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
            console.error("Error fetching stock recommendation:", error);
            displayBotMessage(`<p>I'm sorry, a critical error occurred. Please check the server logs.</p>`);
        } finally {
            loadingIndicator.style.display = 'none';
            userInput.disabled = false;
            sendBtn.disabled = false;
            userInput.focus();
        }
    }
    
    async function handleStockCardClick(event) {
        const card = event.target.closest('.stock-card');
        if (!card || !card.dataset.ticker || card.dataset.ticker === "SYSTEM") return;
        const ticker = card.dataset.ticker;
        modalBody.innerHTML = `<p>Fetching detailed data for ${ticker}...</p>`;
        stockModal.style.display = 'block';
        try {
            const response = await fetch(`/api/get_stock_details/${ticker}`);
            if (!response.ok) throw new Error('Failed to fetch stock details.');
            const data = await response.json();
            populateModal(data);
        } catch (error) {
            modalBody.innerHTML = `<p>Sorry, we could not retrieve the details for ${ticker}.</p>`;
        }
    }

    function displayUserMessage(message) { /* ... (same as before) ... */ }
    function displayBotMessage(text, htmlContent = '') { /* ... (same as before) ... */ }
    
    function createResultsDisplay(data) {
        if (!data || data.length === 0) return "<p>No suitable stocks were found.</p>";

        // --- NEW: Handle System Messages Gracefully ---
        if (data[0].ticker === "SYSTEM") {
            const systemMessage = data[0];
            return `
                <div class="system-card">
                    <div class="card-header">
                        <h3 class="ticker-symbol">System Message</h3>
                        <p class="company-name">${systemMessage.company_name}</p>
                    </div>
                    <div class="card-body">
                        <p class="reason">${systemMessage.reason}</p>
                    </div>
                </div>
            `;
        }

        let cardsHTML = '<div class="results-grid">';
        data.forEach(stock => {
            cardsHTML += `
                <div class="stock-card" data-ticker="${stock.ticker}">
                    <div class="card-header">
                        <h3 class="ticker-symbol">${stock.ticker}</h3>
                        <p class="company-name">${stock.company_name || 'N/A'}</p>
                    </div>
                    <div class="card-body">
                        <p class="reason">${stock.reason}</p>
                    </div>
                </div>
            `;
        });
        cardsHTML += '</div>';
        return cardsHTML;
    }

    function populateModal(data) { /* ... (same as before) ... */ }
    function scrollToBottom() { /* ... (same as before) ... */ }

    // --- PASTE IN THE UNCHANGED FUNCTIONS HERE ---
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
    function populateModal(data) {
        const marketCap = data.marketCap ? (data.marketCap / 1e9).toFixed(2) + 'B' : 'N/A';
        const modalHTML = `<h2>${data.companyName} (${data.ticker})</h2><div class="stock-meta"><span class="meta-item"><strong>Sector:</strong> ${data.sector || 'N/A'}</span><span class="meta-item"><strong>Industry:</strong> ${data.industry || 'N/A'}</span><span class="meta-item"><strong>Market Cap:</strong> ${marketCap}</span><span class="meta-item"><strong>Website:</strong> <a href="${data.website}" target="_blank" rel="noopener noreferrer">${data.website}</a></span></div><p><strong>Description:</strong> ${data.description || 'No description available.'}</p>`;
        modalBody.innerHTML = modalHTML;
    }
    function scrollToBottom() {
        chatWindow.scrollTop = chatWindow.scrollHeight;
    }
});