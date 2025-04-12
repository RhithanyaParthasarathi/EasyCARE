// header.js

// --- Logout Functionality ---
function handleLogout() {
    if (confirm("Are you sure you want to log out?")) {
        console.log("Logging out...");
        localStorage.removeItem('accessToken');
        localStorage.removeItem('userId');
        localStorage.removeItem('userRole');
        localStorage.removeItem('username');
        // Add any other items if needed
        window.location.href = 'login.html'; // Redirect to login
    } else {
        console.log("Logout cancelled.");
    }
}

// Function to attach the handler
function setupLogoutButton(buttonId = 'logout-button') {
     const logoutButton = document.getElementById(buttonId);
     if (logoutButton) {
         logoutButton.addEventListener('click', function(event) {
             console.log("Logout button clicked!"); // DEBUG: Verify listener runs
             event.preventDefault(); // Prevent default anchor tag behavior
             handleLogout();       // Call the logout logic
         });
         console.log("Logout button listener attached to:", buttonId);
     } else {
          // This might appear on pages without the full header/logout button
          // console.warn("Logout button element not found with ID:", buttonId);
     }
}
// --- End Logout ---


// --- DOMContentLoaded Listener ---
document.addEventListener('DOMContentLoaded', function() {
    console.log("Header JS Loaded");

    // --- Menu Dropdown Logic ---
    const menuButton = document.querySelector('.menu-button');
    const menuDropdown = document.querySelector('.menu-dropdown');

    if (menuButton && menuDropdown) {
        menuButton.addEventListener('click', function(event) {
            menuDropdown.classList.toggle('show');
            event.stopPropagation();
        });
        document.addEventListener('click', function(event) {
            if (menuDropdown.classList.contains('show') && !menuButton.contains(event.target) && !menuDropdown.contains(event.target)) {
                menuDropdown.classList.remove('show');
            }
        });
        console.log("Header menu listeners attached.");
    } else {
        console.warn("Header menu button or dropdown not found.");
    }
    // --- End Menu Dropdown Logic ---

    // --- Setup Logout Button ---
    // ** Call setupLogoutButton INSIDE DOMContentLoaded **
    setupLogoutButton();
    // --- End Setup Logout Button ---

    // --- Placeholder for Notification Indicator Logic ---
    // --- Notification Indicator Logic ---
    const API_BASE_URL_HEADER = 'http://127.0.0.1:8000'; // Define Base URL if not already available globally

    // Function to get token (can be defined here or imported if you create shared utils)
    function getAuthTokenHeader() {
        const token = localStorage.getItem('accessToken');
        // Optional: Add a console log here too if needed for debugging header specifically
        // console.log("Header getAuthTokenHeader:", token ? "Found" : "Not Found");
        return token;
    }

    async function updateNotificationIndicator() {
        console.log("Header checking notification indicator..."); // DEBUG
        const indicator = document.getElementById('notification-indicator');
        const notificationLink = document.getElementById('notification-link'); // Get the link itself
        // Check if both elements actually exist on the current page
        if (!indicator || !notificationLink) {
             // console.log("Indicator or link not found in header on this page."); // Normal if header varies
             return;
        }

        const token = getAuthTokenHeader(); // Use the function defined above
        if (!token) {
             indicator.style.display = 'none'; // Hide if not logged in
             notificationLink.classList.remove('has-unread'); // Ensure no highlight class
             console.log("Indicator hidden: No token.");
             return;
        }

        // ** Make sure the prefix here matches your notifications router **
        const apiUrl = `${API_BASE_URL_HEADER}/notifications/unread-count`;
        try {
            const response = await fetch(apiUrl, {
                headers: { 'Authorization': `Bearer ${token}` }
            });

            // Check for auth errors specifically
            if (response.status === 401 || response.status === 403) {
                 console.warn("Auth error fetching unread count for header indicator.");
                 indicator.style.display = 'none';
                 notificationLink.classList.remove('has-unread');
                 // Optionally clear token here too if auth consistently fails
                 // localStorage.removeItem('accessToken');
                 return; // Don't proceed if not authorized
            }
             if (!response.ok) {
                 console.error(`Failed to fetch unread count: ${response.status}`);
                 indicator.style.display = 'none'; // Hide on error
                 notificationLink.classList.remove('has-unread');
                 return;
             }

            const data = await response.json();
            if (data.unread_count > 0) {
                 indicator.style.display = 'block'; // Show dot
                 notificationLink.classList.add('has-unread'); // Optional: add class for styling link/icon
                 console.log("Indicator: Shown (Unread:", data.unread_count, ")");
            } else {
                 indicator.style.display = 'none'; // Hide dot
                 notificationLink.classList.remove('has-unread');
                 console.log("Indicator: Hidden (Unread: 0)");
            }
        } catch (error) {
             console.error("Error updating notification indicator:", error);
             indicator.style.display = 'none'; // Hide on any fetch error
             notificationLink.classList.remove('has-unread');
        }
    }

    // ** Call the function when the header's script loads **
    updateNotificationIndicator();

    // Optional: Update periodically? (Usually not needed unless actions outside the app trigger notifications)
    // setInterval(updateNotificationIndicator, 60000); // e.g., Check every minute

    // --- End Notification Indicator Logic ---
    // --- End Placeholder ---

}); // End DOMContentLoaded