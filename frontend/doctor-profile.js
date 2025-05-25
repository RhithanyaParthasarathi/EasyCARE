// doctor-profile.js

document.addEventListener("DOMContentLoaded", () => {
    console.log("Doctor Profile JS Loaded");
    const form = document.getElementById('doctor-profile-form');
    if (!form) {
        console.error("Doctor profile form not found!");
        return;
    }

    // --- Input Field & Error Span References ---
    const fullNameInput = document.getElementById('fullName');
    const emailInput = document.getElementById('email'); // Probably make readonly
    const specialtyInput = document.getElementById('specialty');
    const hospitalInput = document.getElementById('hospital');
    const licenseNumberInput = document.getElementById('licenseNumber'); // Probably make readonly
    const yearsExperienceInput = document.getElementById('yearsExperience');
    const qualificationsInput = document.getElementById('qualifications');
    const aboutMeInput = document.getElementById('aboutMe');

    // Error spans (assuming IDs match input IDs + "Error")
    const errorSpans = {
        fullName: document.getElementById('fullNameError'),
        email: document.getElementById('emailError'),
        specialty: document.getElementById('specialtyError'),
        hospital: document.getElementById('hospitalError'),
        licenseNumber: document.getElementById('licenseNumberError'),
        yearsExperience: document.getElementById('yearsExperienceError'),
        qualifications: document.getElementById('qualificationsError'),
        aboutMe: document.getElementById('aboutMeError')
    };
    const allInputs = [fullNameInput, emailInput, specialtyInput, hospitalInput, licenseNumberInput, yearsExperienceInput, qualificationsInput, aboutMeInput];

    // Button
    const saveButton = document.getElementById('save-profile-btn');

    // API Base URL
    const API_BASE_URL = 'https://chronicare.onrender.com'; // Adjust if needed

    // --- Helper: Get Auth Token ---
    function getAuthToken() {
        const token = localStorage.getItem('accessToken');
        console.log("Doctor Profile: Token Check - ", token ? "Found" : "Not Found");
        return token;
    }

    // --- Function to Populate Form ---
    function populateForm(data) {
        console.log("Populating doctor form:", data);
        if (!data) return;

        // Populate from User part
        if (emailInput) {
             emailInput.value = data.email || '';
             emailInput.readOnly = true; // Make email readonly
             emailInput.style.backgroundColor = '#e9ecef'; // Indicate readonly
        }
         if (licenseNumberInput) {
             licenseNumberInput.value = data.license_number || '';
             licenseNumberInput.readOnly = true; // Make license readonly
             licenseNumberInput.style.backgroundColor = '#e9ecef'; // Indicate readonly
        }


        // Populate from Profile part (handle nulls)
        const profile = data.profile || {}; // Use empty object if profile is null
        if (fullNameInput) fullNameInput.value = profile.full_name || data.username || ''; // Use full_name or fallback to username
        if (specialtyInput) specialtyInput.value = profile.specialty ?? '';
        if (hospitalInput) hospitalInput.value = profile.hospital_affiliation ?? '';
        if (yearsExperienceInput) yearsExperienceInput.value = profile.years_experience ?? '';
        if (qualificationsInput) qualificationsInput.value = profile.qualifications ?? '';
        if (aboutMeInput) aboutMeInput.value = profile.about_me ?? '';
    }

    // --- Function to Fetch Profile Data ---
    async function fetchProfile() {
        console.log("Fetching doctor profile data...");
        const token = getAuthToken();
        if (!token) {
            alert("You are not logged in. Redirecting to login.");
            window.location.href = 'login.html';
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
             if (data.role !== 'doctor') {
                 console.warn("Non-doctor user accessed doctor profile page. Redirecting.");
                 window.location.href = 'index.html'; // Redirect patient to their dashboard
                 return;
            }
            populateForm(data);

        } catch (error) {
            console.error("Error fetching profile:", error);
            alert(`Error loading profile: ${error.message}`);
            // Maybe disable form on error?
            form.style.opacity = '0.5';
            form.style.pointerEvents = 'none';
        }
    }

    // --- Validation & Error Handling Helpers ---
    function showError(inputElement, errorElement, message) {
        if (inputElement) inputElement.classList.add('input-error');
        if (errorElement) {
            errorElement.textContent = message;
            errorElement.style.display = 'block';
        }
    }

    function clearError(inputElement, errorElement) {
         if (inputElement) inputElement.classList.remove('input-error');
         if (errorElement) errorElement.style.display = 'none';
    }

    function clearAllErrors() {
        Object.keys(errorSpans).forEach(key => {
            const input = document.getElementById(key); // Assuming input ID matches key
            const errorSpan = errorSpans[key];
            if (input && errorSpan) clearError(input, errorSpan);
        });
         // Also clear for specific inputs if IDs don't match keys directly
         if(qualificationsInput && errorSpans.qualifications) clearError(qualificationsInput, errorSpans.qualifications);
         if(aboutMeInput && errorSpans.aboutMe) clearError(aboutMeInput, errorSpans.aboutMe);
    }

    function validateForm() {
        let isValid = true;
        clearAllErrors();

        // Simple required checks - enhance as needed
        if (!fullNameInput?.value.trim()) { showError(fullNameInput, errorSpans.fullName, 'Full Name is required.'); isValid = false; }
        if (!specialtyInput?.value.trim()) { showError(specialtyInput, errorSpans.specialty, 'Specialty is required.'); isValid = false; }
        // Email/License are readonly, maybe skip validation or just check existence
        if (!hospitalInput?.value.trim()) { showError(hospitalInput, errorSpans.hospital, 'Hospital/Clinic is required.'); isValid = false; }
        const years = yearsExperienceInput?.value;
        if (years === '' || years === null) { showError(yearsExperienceInput, errorSpans.yearsExperience, 'Years of Experience is required.'); isValid = false;}
        else if (isNaN(years) || parseInt(years, 10) < 0) { showError(yearsExperienceInput, errorSpans.yearsExperience, 'Years must be 0 or more.'); isValid = false;}
        if (!qualificationsInput?.value.trim()) { showError(qualificationsInput, errorSpans.qualifications, 'Qualifications are required.'); isValid = false; }
        if (!aboutMeInput?.value.trim()) { showError(aboutMeInput, errorSpans.aboutMe, 'A brief bio is required.'); isValid = false; }

        return isValid;
    }


    // --- Form Submission Handler ---
    form.addEventListener('submit', async function(event) {
        event.preventDefault();
        console.log("Doctor profile form submitted.");

        if (validateForm()) {
            console.log("Doctor profile validation successful!");
            const token = getAuthToken();
            if (!token) {
                alert("Authentication error. Please log in again.");
                return;
            }

            // Prepare payload - only include fields for DoctorProfileUpdate
            const payload = {
                full_name: fullNameInput.value.trim(),
                specialty: specialtyInput.value.trim(),
                hospital_affiliation: hospitalInput.value.trim(),
                years_experience: parseInt(yearsExperienceInput.value) || 0, // Default to 0 if empty/invalid
                qualifications: qualificationsInput.value.trim(),
                about_me: aboutMeInput.value.trim()
                // Do NOT send email or license number if they are not editable
            };
            console.log("Saving doctor payload:", payload);

            const apiUrl = `${API_BASE_URL}/profile/me/doctor`; // Doctor-specific endpoint
            if(saveButton) {
                 saveButton.disabled = true;
                 saveButton.textContent = 'Saving...';
            }

            try {
                const response = await fetch(apiUrl, {
                    method: 'PUT',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${token}`
                    },
                    body: JSON.stringify(payload)
                });

                const data = await response.json();

                if (!response.ok) {
                     if (response.status === 401 || response.status === 403) localStorage.removeItem('accessToken');
                    throw new Error(data.detail || `Failed to save profile (${response.status})`);
                }

                console.log("Doctor profile save successful:", data);
                alert("Profile updated successfully!");
                // Re-populate form with potentially updated data (like is_complete flag)
                populateForm(data);

                 // Optionally trigger prompt check again
                 if (typeof checkAndShowProfilePrompt === 'function') {
                     checkAndShowProfilePrompt();
                 }

            } catch (error) {
                console.error("Error saving doctor profile:", error);
                alert(`Error saving profile: ${error.message}`);
            } finally {
                 if(saveButton) {
                      saveButton.disabled = false;
                      saveButton.textContent = 'Save Profile';
                 }
            }

        } else {
            console.log("Doctor profile validation failed.");
            // alert("Please correct the errors in the form."); // Alert can be annoying
        }
    });

    // --- Optional: Clear errors on input ---
    allInputs.forEach(input => {
         if (input) {
             input.addEventListener('input', () => {
                 const errorElement = errorSpans[input.id]; // Assumes error span ID matches input ID + "Error"
                 if (errorElement) {
                      clearError(input, errorElement);
                 } else { // Fallback for textareas maybe
                     const textareaError = errorSpans[input.id.replace('Input','')]; // Crude guess
                     if(textareaError) clearError(input, textareaError);
                 }
             });
         }
    });

    // --- Initial Load ---
    fetchProfile(); // Fetch data when the page loads

}); // End DOMContentLoaded