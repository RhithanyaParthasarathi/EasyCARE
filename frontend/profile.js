// profile.js

document.addEventListener("DOMContentLoaded", function() {
    console.log("Profile.js Loaded");

    // --- DOM Elements ---
    // Spans for displaying data
    const nameSpan = document.getElementById("user-name");
    const emailSpan = document.getElementById("user-email");
    const ageSpan = document.getElementById("user-age");
    const genderSpan = document.getElementById("user-gender");
    const heightSpan = document.getElementById("user-height");
    const weightSpan = document.getElementById("user-weight");
    const bloodTypeSpan = document.getElementById("user-blood-type");

    // Inputs/Selects for editing data
    const nameInput = document.getElementById("edit-name");
    const emailInput = document.getElementById("edit-email"); // Consider making this readonly
    const ageInput = document.getElementById("edit-age");
    const genderSelect = document.getElementById("edit-gender");
    const heightInput = document.getElementById("edit-height");
    const weightInput = document.getElementById("edit-weight");
    const bloodTypeSelect = document.getElementById("edit-blood-type");
    const allSpans = [nameSpan, emailSpan, ageSpan, genderSpan, heightSpan, weightSpan, bloodTypeSpan];
    const allInputs = [nameInput, emailInput, ageInput, genderSelect, heightInput, weightInput, bloodTypeSelect];

    // Buttons
    const editButton = document.getElementById("edit-profile-btn");
    const saveButton = document.getElementById("save-profile-btn");

    // API Base URL
    const API_BASE_URL = 'https://chronicare.onrender.com'; // Adjust if needed

    // --- Helper: Get Auth Token ---
    function getAuthToken() {
        const token = localStorage.getItem('accessToken');
        console.log("Profile Page: Token Check - ", token ? "Found" : "Not Found");
        return token;
    }

    // --- Function to Toggle Edit/View Mode ---
    function toggleEditMode(isEditing) {
        allSpans.forEach(span => span.style.display = isEditing ? "none" : "inline");
        allInputs.forEach(input => input.style.display = isEditing ? "inline-block" : "none"); // Use inline-block for inputs/selects
        if(editButton) editButton.style.display = isEditing ? "none" : "inline-block";
        if(saveButton) saveButton.style.display = isEditing ? "inline-block" : "none";
    }

    // --- Function to Populate Form/Spans ---
    function populateProfileData(data) {
        console.log("Populating profile data:", data);
        // Populate from User part
        if (nameSpan) nameSpan.textContent = data.profile?.full_name || data.username || 'N/A'; // Use full_name from profile if available, else username
        if (emailSpan) emailSpan.textContent = data.email || 'N/A';
        if (nameInput) nameInput.value = data.profile?.full_name || data.username || ''; // Pre-fill input too
        if (emailInput) {
             emailInput.value = data.email || '';
             // ** Consider making email readonly after first fetch **
             // emailInput.readOnly = true;
        }


        // Populate from Profile part (handle nulls)
        const profile = data.profile || {}; // Use empty object if profile is null
        if (ageSpan) ageSpan.textContent = profile.age ?? 'N/A'; // Use ?? for nullish coalescing
        if (genderSpan) genderSpan.textContent = profile.gender ?? 'N/A';
        if (heightSpan) heightSpan.textContent = profile.height_cm ?? 'N/A';
        if (weightSpan) weightSpan.textContent = profile.weight_kg ?? 'N/A';
        if (bloodTypeSpan) bloodTypeSpan.textContent = profile.blood_type ?? 'N/A';

        // Pre-fill inputs/selects for edit mode
        if (ageInput) ageInput.value = profile.age ?? '';
        if (genderSelect) genderSelect.value = profile.gender ?? ''; // Ensure options match possible values
        if (heightInput) heightInput.value = profile.height_cm ?? '';
        if (weightInput) weightInput.value = profile.weight_kg ?? '';
        if (bloodTypeSelect) bloodTypeSelect.value = profile.blood_type ?? '';

        // Initial state is view mode
        toggleEditMode(false);
    }

    // --- Function to Fetch Profile Data ---
    async function fetchProfile() {
        console.log("Fetching profile data...");
        const token = getAuthToken();
        if (!token) {
            alert("You are not logged in. Redirecting to login.");
            window.location.href = 'login.html'; // Redirect if no token
            return;
        }

        const apiUrl = `${API_BASE_URL}/profile/me`;
        try {
            const response = await fetch(apiUrl, {
                method: 'GET',
                headers: { 'Authorization': `Bearer ${token}` }
            });

            if (response.status === 401 || response.status === 403) {
                localStorage.removeItem('accessToken');
                throw new Error("Authentication failed. Please log in again.");
            }
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || `Failed to fetch profile (${response.status})`);
            }

            const data = await response.json();
            if (data.role !== 'patient') {
                 // If somehow a doctor lands here, redirect them
                 console.warn("Non-patient user accessed patient profile page. Redirecting.");
                 window.location.href = 'doctor-dashboard.html'; // Or appropriate page
                 return;
            }
            populateProfileData(data);

        } catch (error) {
            console.error("Error fetching profile:", error);
            alert(`Error loading profile: ${error.message}`);
            // Handle error - maybe show message, redirect to login?
            document.querySelector('#profile-info').innerHTML = `<p style="color:red;">Could not load profile data.</p>`;
        }
    }

    // --- Function to Save Profile Data ---
    async function saveProfile() {
        console.log("Attempting to save profile...");

        // --- *** ADD VALIDATION HERE *** ---
    let isValid = true;
    // Clear previous errors visually (optional)
    allInputs.forEach(input => input.classList.remove('input-error')); // Simple visual clear

    // Example: Check required fields (adjust based on what IS required for a patient)
    if (!nameInput.value.trim()) {
        alert("Full Name cannot be empty."); // Simple alert for now
        nameInput.classList.add('input-error'); // Highlight field
        isValid = false;
    }
    if (!ageInput.value.trim()) { // Check if age is required
         alert("Age cannot be empty.");
         ageInput.classList.add('input-error');
         isValid = false;
    } else if (isNaN(parseInt(ageInput.value)) || parseInt(ageInput.value) <= 0) {
        alert("Please enter a valid positive number for age.");
        ageInput.classList.add('input-error');
        isValid = false;
    }
     // Add similar checks for other fields you deem MANDATORY for a patient profile
     // e.g., gender, height, weight?

    if (!isValid) {
        console.log("Client-side validation failed.");
        return; // Stop if validation fails
    }
    // --- *** END VALIDATION *** ---

        const token = getAuthToken();
        if (!token) {
            alert("Authentication error. Please log in again.");
            return;
        }

        // Prepare payload - only include fields for PatientProfileUpdate
        const payload = {
            full_name: nameInput.value.trim(),
            age: parseInt(ageInput.value) || null, // Send null if empty/invalid number
            gender: genderSelect.value || null,
            height_cm: parseInt(heightInput.value) || null,
            weight_kg: parseFloat(weightInput.value) || null, // Use parseFloat
            blood_type: bloodTypeSelect.value || null
            // Email is usually not updated here unless verified
        };
        // Remove null values if backend expects only provided fields (optional)
        // Object.keys(payload).forEach(key => payload[key] == null && delete payload[key]);

        console.log("Saving payload:", payload);

        const apiUrl = `${API_BASE_URL}/profile/me/patient`; // Use patient-specific endpoint
        saveButton.disabled = true; // Disable button during save
        saveButton.textContent = 'Saving...';

        try {
            const response = await fetch(apiUrl, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify(payload)
            });

            const data = await response.json(); // Try to parse response always

            if (!response.ok) {
                if (response.status === 401 || response.status === 403) localStorage.removeItem('accessToken');
                throw new Error(data.detail || `Failed to save profile (${response.status})`);
            }

            console.log("Save successful:", data);
            alert("Profile updated successfully!");
            populateProfileData(data); // Re-populate with confirmed data from response
            toggleEditMode(false); // Switch back to view mode

            // Optionally trigger prompt check again if header.js function is available globally
             if (typeof checkAndShowProfilePrompt === 'function') {
                 checkAndShowProfilePrompt();
             }


        } catch (error) {
            console.error("Error saving profile:", error);
            alert(`Error saving profile: ${error.message}`);
            // Don't switch mode on error, let user correct
        } finally {
             saveButton.disabled = false; // Re-enable button
             saveButton.textContent = 'Save Changes';
        }
    }


    // --- Event Listeners ---
    if (editButton) {
        editButton.addEventListener("click", () => {
            // Before entering edit mode, ensure inputs have latest data (in case fetch updated spans)
             const profileDataForEdit = {
                  profile: {
                       full_name: nameSpan.textContent === 'N/A' ? '' : nameSpan.textContent,
                       age: ageSpan.textContent === 'N/A' ? '' : ageSpan.textContent,
                       gender: genderSpan.textContent === 'N/A' ? '' : genderSpan.textContent,
                       height_cm: heightSpan.textContent === 'N/A' ? '' : heightSpan.textContent,
                       weight_kg: weightSpan.textContent === 'N/A' ? '' : weightSpan.textContent,
                       blood_type: bloodTypeSpan.textContent === 'N/A' ? '' : bloodTypeSpan.textContent,
                  },
                  email: emailSpan.textContent === 'N/A' ? '' : emailSpan.textContent
             };
             populateProfileData(profileDataForEdit); // This call now mainly sets input values
            toggleEditMode(true); // Then switch to edit mode
        });
    }

    if (saveButton) {
        saveButton.addEventListener("click", saveProfile);
    }

    // --- Initial Load ---
    fetchProfile(); // Fetch data when the page loads

}); // End DOMContentLoaded