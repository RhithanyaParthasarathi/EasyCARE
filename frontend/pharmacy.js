document.addEventListener('DOMContentLoaded', function() {
    const searchInput = document.getElementById('medicine-search');
    const searchButton = document.getElementById('search-button');
    const pharmacyListDiv = document.getElementById('pharmacy-list');
    const defaultSuggestionsDiv = document.getElementById('default-suggestions');

    // Function to display pharmacies based on medicine name
    function displayPharmacies(medicineName) {
        const pharmacies = getPharmaciesForMedicine(medicineName);

        if (pharmacies && pharmacies.length > 0) {
            let pharmacyItemsHTML = "";
            pharmacies.forEach(pharmacy => {
                pharmacyItemsHTML += `
                    <div class="pharmacy-item">
                        <h3>${pharmacy.name}</h3>
                        <p>Address: ${pharmacy.address}</p>
                        <p>Distance: ${pharmacy.distance}</p>
                        <button class="order-button" data-pharmacy="${pharmacy.name}" data-medicine="${medicineName}">Order Medicine</button>
                    </div>
                `;
            });
            pharmacyListDiv.innerHTML = pharmacyItemsHTML;

            // Add event listeners to order buttons
            document.querySelectorAll('.order-button').forEach(button => {
                button.addEventListener('click', function() {
                    const pharmacyName = this.dataset.pharmacy;
                    const medicine = this.dataset.medicine;
                    alert(`Ordering ${medicine} from ${pharmacyName} (Not Implemented)`);
                    // In a real app, you'd handle the order placement logic here
                });
            });
        } else {
            pharmacyListDiv.textContent = `No pharmacies found with ${medicineName} nearby.`;
        }
    }

    // Function to display default suggestions
    function displayDefaultSuggestions() {
        const suggestionsHTML = `
            <p>Try searching for:
                <a href="#" data-medicine="Amoxicillin" class="suggestion-link">Amoxicillin</a>
                <a href="#" data-medicine="Lisinopril" class="suggestion-link">Lisinopril</a>
                <a href="#" data-medicine="Atorvastatin" class="suggestion-link">Atorvastatin</a>
                <a href="#" data-medicine="Aspirin" class="suggestion-link">Aspirin</a>
            </p>
        `;
        pharmacyListDiv.innerHTML = suggestionsHTML;

        // Add event listeners to suggestion links
        document.querySelectorAll('.suggestion-link').forEach(link => {
            link.addEventListener('click', function(event) {
                event.preventDefault();
                const medicine = this.dataset.medicine;
                searchInput.value = medicine;
                displayPharmacies(medicine);
            });
        });
    }

    searchButton.addEventListener('click', function() {
        const medicineName = searchInput.value.trim();

        if (medicineName === "") {
            displayDefaultSuggestions();
        } else {
            displayPharmacies(medicineName);
        }
    });

    searchInput.addEventListener('input', function() {
        if (this.value.trim() === "") {
            displayDefaultSuggestions();
        }
    });

    // Dummy function to simulate fetching pharmacies for a given medicine
    function getPharmaciesForMedicine(medicineName) {
        // Replace this with actual API calls in a real application
        const pharmacyData = [
            { name: "City Pharmacy", address: "123 Main St", distance: "0.5 miles", medicines: ["Amoxicillin", "Lisinopril"] },
            { name: "CarePlus Pharmacy", address: "456 Oak Ave", distance: "1.2 miles", medicines: ["Atorvastatin", "Lisinopril"] },
            { name: "Green Cross Pharmacy", address: "789 Pine Ln", distance: "2.0 miles", medicines: ["Amoxicillin", "Aspirin"] }
        ];

        return pharmacyData.filter(pharmacy => pharmacy.medicines.includes(medicineName));
    }

    // Initial display (show default suggestions on page load)
    displayDefaultSuggestions();
});