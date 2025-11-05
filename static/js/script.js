/* /static/js/script.js */

// Wait for the entire HTML document to be loaded and parsed
document.addEventListener('DOMContentLoaded', () => {

    // --- DOM Element Selection ---
    const chatWindow = document.getElementById('chat-window');
    const userInput = document.getElementById('user-input');
    const sendBtn = document.getElementById('send-btn');
    const loadingIndicator = document.getElementById('loading-indicator');
    const resultsArea = document.getElementById('results-area');
    const stockModal = document.getElementById('stock-modal');
    const modalCloseBtn = document.querySelector('.close-button');
    const modalBody = document.getElementById('modal-body');

    // --- Event Listeners ---

    // Listen for clicks on the send button
    sendBtn.addEventListener('click', handleUserQuery);
    
    // Listen for the "Enter" key press in the text area
    userInput.addEventListener('keydown', (event) => {
        if (event.key === 'Enter' && !event.shiftKey) {
            event.preventDefault(); // Prevents new line on Enter
            handleUserQuery();
        }
    });

    // Listen for clicks on the modal's close button
    modalCloseBtn.addEventListener('click', () => {
        stockModal.style.display = 'none';
    });

    // Listen for clicks outside the modal content to close it
    window.addEventListener('click', (event) => {
        if (event.target == stockModal) {
            stockModal.style.display = 'none';
        }
    });
    
    // Listen for clicks on the results area (for clicking on stock rows)
    resultsArea.addEventListener('click', handleStockRowClick);


    // --- Core Functions ---

    /**
     * Main function to handle the user's query submission.
     */
    async function handleUserQuery() {
        const query = userInput.value.trim();
        if (!query) return; // Do nothing if input is empty

        displayUserMessage(query);
        userInput.value = ''; // Clear the input field
        userInput.disabled = true; // Disable input during processing
        sendBtn.disabled = true;

        loadingIndicator.style.display = 'block';
        resultsArea.style.display = 'none'; // Hide previous results
        resultsArea.innerHTML = '';

        try {
            // --- Fetch AI Recommendation from our Backend ---
            const response = await fetch('/api/get_stock_recommendation', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ query: query }),
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();

            // Display the results in a beautiful table
            displayBotMessage(createResultsTable(data));

        } catch (error) {
            console.error("Error fetching stock recommendation:", error);
            displayBotMessage("<p>I'm sorry, an error occurred while analyzing the data. Please try again.</p>");
        } finally {
            // --- Cleanup ---
            loadingIndicator.style.display = 'none';
            userInput.disabled = false; // Re-enable input
            sendBtn.disabled = false;
            userInput.focus(); // Set focus back to input
        }
    }
    
    /**
     * Handles clicking on a stock row in the results table.
     * @param {Event} event - The click event.
     */
    async function handleStockRowClick(event) {
        const row = event.target.closest('tr');
        if (!row || !row.dataset.ticker) return; // Ensure a valid row was clicked

        const ticker = row.dataset.ticker;
        
        // Show the modal with a loading state
        modalBody.innerHTML = `<p>Fetching detailed data for ${ticker}...</p>`;
        stockModal.style.display = 'block';

        try {
            // We will build this new API endpoint in the next step
            // For now, the JS is ready for it.
            const response = await fetch(`/api/get_stock_details/${ticker}`);
            if (!response.ok) {
                throw new Error('Failed to fetch stock details.');
            }
            const data = await response.json();
            populateModal(data);

        } catch (error) {
            console.error('Error fetching stock details:', error);
            modalBody.innerHTML = `<p>Sorry, we could not retrieve the details for ${ticker}.</p>`;
        }
    }


    // --- Display & UI Functions ---

    /**
     * Displays the user's message in the chat window.
     * @param {string} message - The text message from the user.
     */
    function displayUserMessage(message) {
        const messageElement = document.createElement('div');
        messageElement.className = 'chat-message user-message';
        messageElement.innerHTML = `<p class="message-text">${message}</p>`;
        chatWindow.appendChild(messageElement);
        scrollToBottom();
    }

    /**
     * Displays a message from the bot, which can contain HTML.
     * @param {string} htmlContent - The HTML content to display.
     */
    function displayBotMessage(htmlContent) {
        const messageElement = document.createElement('div');
        messageElement.className = 'chat-message bot-message';
        messageElement.innerHTML = htmlContent;
        chatWindow.appendChild(messageElement);
        scrollToBottom();
    }
    
    /**
     * Creates and returns the HTML for the results table.
     * @param {Array} data - The array of stock objects from the AI.
     * @returns {string} The HTML string for the table.
     */
    function createResultsTable(data) {
        if (!data || data.length === 0) {
            return "<p>No suitable stocks were found based on your criteria.</p>";
        }

        let tableHTML = `
            <p>Here are the top recommendations based on my analysis. Click on any stock for a detailed view:</p>
            <table class="results-table">
                <thead>
                    <tr>
                        <th>Ticker</th>
                        <th>Company Name</th>
                        <th>Reason for Recommendation</th>
                    </tr>
                </thead>
                <tbody>
        `;

        data.forEach(stock => {
            tableHTML += `
                <tr data-ticker="${stock.ticker}">
                    <td class="ticker">${stock.ticker}</td>
                    <td>${stock.company_name}</td>
                    <td>${stock.reason}</td>
                </tr>
            `;
        });

        tableHTML += '</tbody></table>';
        resultsArea.innerHTML = tableHTML;
        resultsArea.style.display = 'block';
        scrollToBottom();
        // The table is returned to be placed in a bot message if needed,
        // but the primary action is to inject it directly into resultsArea.
        // For simplicity, we'll return an empty string as the content is already on the page.
        return "Here are my findings. Please see the table below for details.";
    }

    /**
     * Populates the modal with detailed stock information.
     * @param {object} data - The detailed stock data object.
     */
    function populateModal(data) {
        const marketCap = data.marketCap ? (data.marketCap / 1e9).toFixed(2) + 'B' : 'N/A';
        const modalHTML = `
            <h2>${data.companyName} (${data.ticker})</h2>
            <div class="stock-meta">
                <span class="meta-item"><strong>Sector:</strong> ${data.sector || 'N/A'}</span>
                <span class="meta-item"><strong>Industry:</strong> ${data.industry || 'N/A'}</span>
                <span class="meta-item"><strong>Market Cap:</strong> ${marketCap}</span>
                <span class="meta-item"><strong>Website:</strong> <a href="${data.website}" target="_blank">${data.website}</a></span>
            </div>
            <p><strong>Description:</strong> ${data.description || 'No description available.'}</p>
        `;
        modalBody.innerHTML = modalHTML;
    }

    /**
     * Helper function to scroll the chat window to the bottom.
     */
    function scrollToBottom() {
        chatWindow.scrollTop = chatWindow.scrollHeight;
    }

});