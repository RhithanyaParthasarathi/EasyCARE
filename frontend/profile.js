document.addEventListener("DOMContentLoaded", function() {
    const editButton = document.getElementById("edit-profile-btn");
    const saveButton = document.getElementById("save-profile-btn");

    const nameSpan = document.getElementById("user-name");
    const ageSpan = document.getElementById("user-age");
    const emailSpan = document.getElementById("user-email");
    const genderSpan = document.getElementById("user-gender");
    const heightSpan = document.getElementById("user-height");
    const weightSpan = document.getElementById("user-weight");
    const bloodTypeSpan = document.getElementById("user-blood-type");

    const nameInput = document.getElementById("edit-name");
    const ageInput = document.getElementById("edit-age");
    const emailInput = document.getElementById("edit-email");
    const genderSelect = document.getElementById("edit-gender");
    const heightInput = document.getElementById("edit-height");
    const weightInput = document.getElementById("edit-weight");
    const bloodTypeSelect = document.getElementById("edit-blood-type");

    editButton.addEventListener("click", function() {
        // Show input fields
        nameInput.value = nameSpan.textContent;
        ageInput.value = ageSpan.textContent;
        emailInput.value = emailSpan.textContent;
        genderSelect.value = genderSpan.textContent;
        heightInput.value = heightSpan.textContent;
        weightInput.value = weightSpan.textContent;
        bloodTypeSelect.value = bloodTypeSpan.textContent;

        nameSpan.style.display = "none";
        ageSpan.style.display = "none";
        emailSpan.style.display = "none";
        genderSpan.style.display = "none";
        heightSpan.style.display = "none";
        weightSpan.style.display = "none";
        bloodTypeSpan.style.display = "none";

        nameInput.style.display = "inline";
        ageInput.style.display = "inline";
        emailInput.style.display = "inline";
        genderSelect.style.display = "inline";
        heightInput.style.display = "inline";
        weightInput.style.display = "inline";
        bloodTypeSelect.style.display = "inline";

        editButton.style.display = "none";
        saveButton.style.display = "inline";
    });

    saveButton.addEventListener("click", function() {
        // Save changes
        nameSpan.textContent = nameInput.value;
        ageSpan.textContent = ageInput.value;
        emailSpan.textContent = emailInput.value;
        genderSpan.textContent = genderSelect.value;
        heightSpan.textContent = heightInput.value;
        weightSpan.textContent = weightInput.value;
        bloodTypeSpan.textContent = bloodTypeSelect.value;

        nameSpan.style.display = "inline";
        ageSpan.style.display = "inline";
        emailSpan.style.display = "inline";
        genderSpan.style.display = "inline";
        heightSpan.style.display = "inline";
        weightSpan.style.display = "inline";
        bloodTypeSpan.style.display = "inline";

        nameInput.style.display = "none";
        ageInput.style.display = "none";
        emailInput.style.display = "none";
        genderSelect.style.display = "none";
        heightInput.style.display = "none";
        weightInput.style.display = "none";
        bloodTypeSelect.style.display = "none";

        editButton.style.display = "inline";
        saveButton.style.display = "none";
    });
});