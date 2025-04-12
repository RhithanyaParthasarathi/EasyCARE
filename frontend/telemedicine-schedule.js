document.addEventListener('DOMContentLoaded', function() {
    // --- DOM Elements ---
    const currentMonthSpan = document.getElementById('current-month');
    const calendarGridDiv = document.getElementById('calendar-grid');
    const prevMonthButton = document.getElementById('prev-month');
    const nextMonthButton = document.getElementById('next-month');
    const timeSlotDivs = {
        morning: document.querySelector('.time-slots.morning'),
        afternoon: document.querySelector('.time-slots.afternoon'),
        evening: document.querySelector('.time-slots.evening'),
        night: document.querySelector('.time-slots.night')
    };
    const hourInput = document.getElementById('hourInput');
    const minuteInput = document.getElementById('minuteInput');
    const ampmSelect = document.getElementById('ampmSelect');
    const addTimeslotButton = document.getElementById('addTimeslotButton');
    const selectedDateDisplay = document.getElementById('selected-date-display');
    const selectedSlotsDisplay = document.getElementById('selected-slots-display');
    const saveScheduleButton = document.getElementById('save-schedule-button');
    const deleteScheduleButton = document.getElementById('delete-schedule-button');
    const loadingMessage = document.getElementById('loading-message');

    // --- State Variables ---
    let currentCalendarDate = new Date();
    let selectedDate = null; // JS Date object
    let currentDaySlots = {}; // Format: { 'HH:MM': { saved: boolean, selected: boolean } }
    const API_BASE_URL = 'http://127.0.0.1:8000/appointments'; // Adjust if needed

    // --- Default Slot Definitions ---
    const defaultTimeSlots = {
        morning: ["08:00", "08:30", "09:00", "09:30", "10:00", "10:30", "11:00", "11:30"],
        afternoon: ["12:00", "12:30", "13:00", "13:30", "14:00", "14:30", "15:00", "15:30", "16:00", "16:30"],
        evening: ["17:00", "17:30", "18:00", "18:30", "19:00", "19:30", "20:00", "20:30"],
        night: ["21:00", "21:30", "22:00", "22:30"]
    };

    // --- Helper Functions ---

    function getAuthToken() {
        const token = localStorage.getItem('accessToken');
        console.log("getAuthToken: Token from localStorage:", token ? `${token.substring(0, 10)}...` : null); // DEBUG
        return token;
    }

    function convertTo12Hour(time24) {
        if (!time24 || !time24.includes(':')) return "Invalid Time";
        const [hours, minutes] = time24.split(':');
        let hoursInt = parseInt(hours);
        const ampm = hoursInt >= 12 ? 'PM' : 'AM';
        hoursInt = hoursInt % 12;
        hoursInt = hoursInt || 12; // Handle midnight
        return `${hoursInt}:${minutes} ${ampm}`;
    }

    function determineTimeSection(time24) {
        const [hours] = time24.split(':');
        const hour = parseInt(hours);
        if (hour >= 5 && hour < 12) return 'morning';
        if (hour >= 12 && hour < 17) return 'afternoon';
        if (hour >= 17 && hour < 21) return 'evening';
        if (hour >= 21 || hour < 5) return 'night';
        console.warn("Could not determine section for time:", time24); // Warn if no section found
        return null;
    }

    function compareTimes(timeA, timeB) {
        return timeA.localeCompare(timeB);
    }

   // --- REPLACE formatDateISO AGAIN with this version ---
function formatDateISO(date) {
    if (!date || !(date instanceof Date)) {
        console.error("Invalid date passed to formatDateISO:", date);
        return '';
    }
    try {
        // Create a NEW Date object using UTC values to prevent timezone shifts during formatting
        const year = date.getFullYear();
        const month = date.getMonth(); // 0-indexed
        const day = date.getDate();
        // Constructing a date with UTC ensures it represents the intended day regardless of local offset
        const utcDate = new Date(Date.UTC(year, month, day));

        // Now format this UTC-based date using a reliable method
        const formattedYear = utcDate.getUTCFullYear();
        const formattedMonth = String(utcDate.getUTCMonth() + 1).padStart(2, '0'); // getUTCMonth is also 0-indexed
        const formattedDay = String(utcDate.getUTCDate()).padStart(2, '0');

        const result = `${formattedYear}-${formattedMonth}-${formattedDay}`;
        console.log(`formatDateISO: Input: ${date.toString()}, Output: ${result}`); // DEBUG log the conversion
        return result;

    } catch (e) {
        console.error("Error formatting date components:", date, e);
        return '';
    }
}

    function sortButtonsInSection(sectionDiv) {
        if (!sectionDiv) return;
        const buttons = Array.from(sectionDiv.querySelectorAll('button'));
        buttons.sort((a, b) => compareTimes(a.dataset.time, b.dataset.time));
        buttons.forEach(button => sectionDiv.appendChild(button));
    }

    // --- Initialization & Event Listeners ---
    console.log("DOM Loaded. Setting up listeners..."); // DEBUG
    setupEventListeners();
    updateButtonStates();
    console.log("Attempting initial calendar generation..."); // DEBUG
    generateCalendar(currentCalendarDate.getFullYear(), currentCalendarDate.getMonth());
    console.log("Initial calendar generation function called."); // DEBUG

    function setupEventListeners() {
        prevMonthButton.addEventListener('click', () => changeMonth(-1));
        nextMonthButton.addEventListener('click', () => changeMonth(1));
        addTimeslotButton.addEventListener('click', handleAddTimeslot);
        saveScheduleButton.addEventListener('click', handleSaveSchedule);
        deleteScheduleButton.addEventListener('click', handleDeleteSchedule);
        console.log("Event listeners set up."); // DEBUG
    }

    // --- UI Update Functions ---
    function updateButtonStates() {
        const hasSelection = selectedDate !== null;
        saveScheduleButton.disabled = !hasSelection;
        deleteScheduleButton.disabled = !hasSelection;
        // console.log("Button states updated. Has selection:", hasSelection); // DEBUG Frequent log
    }

    function updateSelectedDateDisplay() {
        if (selectedDate) {
            selectedDateDisplay.textContent = selectedDate.toLocaleDateString('en-US', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' });
        } else {
            selectedDateDisplay.textContent = "No date selected";
        }
        updateSelectedSlotsDisplay(); // Also update the summary text
        updateButtonStates();
    }

    // Complete version of this function
    function updateSelectedSlotsDisplay() {
        selectedSlotsDisplay.innerHTML = '';
        if (!selectedDate) {
            selectedSlotsDisplay.textContent = "Select a date to see/manage schedule.";
            return;
        }
        const selectedTimes = Object.entries(currentDaySlots)
            .filter(([time, state]) => state.selected)
            .map(([time, state]) => time)
            .sort(compareTimes);

        if (selectedTimes.length === 0) {
            selectedSlotsDisplay.textContent = "No time slots selected for this date.";
            return;
        }

        const groupedTimes = { morning: [], afternoon: [], evening: [], night: [] };
        selectedTimes.forEach(time => {
            const section = determineTimeSection(time);
            if (section && groupedTimes.hasOwnProperty(section)) {
                groupedTimes[section].push(time);
            } else {
                console.warn(`Could not group time ${time} into a section for summary.`);
            }
        });

        let contentAdded = false;
        for (const section in groupedTimes) {
            if (groupedTimes[section].length > 0) {
                contentAdded = true;
                const sectionHeader = document.createElement('h5');
                sectionHeader.textContent = section.charAt(0).toUpperCase() + section.slice(1);
                sectionHeader.style.marginTop = '10px';
                selectedSlotsDisplay.appendChild(sectionHeader);

                const timeList = document.createElement('ul');
                timeList.style.listStyle = 'none';
                timeList.style.paddingLeft = '10px';

                groupedTimes[section].forEach(time => {
                    const timeItem = document.createElement('li');
                    timeItem.textContent = convertTo12Hour(time); // Display AM/PM
                    timeItem.style.marginBottom = '3px';
                    timeList.appendChild(timeItem);
                });
                selectedSlotsDisplay.appendChild(timeList);
            }
        }
        if (!contentAdded) {
            selectedSlotsDisplay.textContent = "No time slots selected for this date.";
        }
    }

    function clearTimeSlotsDisplay() {
        Object.values(timeSlotDivs).forEach(div => {
            if(div) div.innerHTML = '';
        });
        selectedSlotsDisplay.innerHTML = 'No time slots selected/loaded.';
        currentDaySlots = {};
        // console.log("Time slots display cleared."); // DEBUG Frequent log
    }

    // --- Calendar Functions ---
    function changeMonth(monthOffset) {
        currentCalendarDate.setMonth(currentCalendarDate.getMonth() + monthOffset);
        generateCalendar(currentCalendarDate.getFullYear(), currentCalendarDate.getMonth());
        selectedDate = null;
        clearTimeSlotsDisplay();
        updateSelectedDateDisplay();
    }

    function generateCalendar(year, month) {
        console.log(`--- generateCalendar called for ${year}-${month + 1} ---`); // DEBUG
        try {
            const firstDayOfMonth = new Date(year, month, 1);
            const lastDayOfMonth = new Date(year, month + 1, 0);
            const daysInMonth = lastDayOfMonth.getDate();
            const startingDayOfWeek = firstDayOfMonth.getDay(); // 0=Sun

            console.log(`Days: ${daysInMonth}, Starting Day: ${startingDayOfWeek}`); // DEBUG

            if (!currentMonthSpan || !calendarGridDiv) {
                 console.error("Calendar DOM elements not found!"); // DEBUG ERROR
                 return;
            }

            currentMonthSpan.textContent = firstDayOfMonth.toLocaleString('default', { month: 'long', year: 'numeric' });
            calendarGridDiv.innerHTML = ''; // Clear previous grid
            console.log("Calendar grid cleared."); // DEBUG

            const weekdays = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
            weekdays.forEach(day => {
                const dayHeader = document.createElement('div');
                dayHeader.classList.add('calendar-weekday');
                dayHeader.textContent = day;
                calendarGridDiv.appendChild(dayHeader);
            });
            console.log("Weekday headers added."); // DEBUG

            for (let i = 0; i < startingDayOfWeek; i++) {
                const emptyDiv = document.createElement('div');
                emptyDiv.classList.add('calendar-day', 'empty'); // Add empty class
                calendarGridDiv.appendChild(emptyDiv);
            }
            console.log(`Added ${startingDayOfWeek} empty cells.`); // DEBUG

            const today = new Date();
            today.setHours(0, 0, 0, 0);

            let daysAdded = 0; // DEBUG counter
            for (let i = 1; i <= daysInMonth; i++) {
                const dayDate = new Date(year, month, i);
                const dateDiv = document.createElement('div');
                dateDiv.classList.add('calendar-day');
                dateDiv.textContent = i;
                const isoDate = formatDateISO(dayDate);
                if (isoDate) { // Only add data-date if formatting is successful
                   dateDiv.dataset.date = isoDate;
                } else {
                   console.warn(`Could not format date for day ${i}`);
                   continue; // Skip this day if date is invalid
                }


                if (dayDate < today) {
                    dateDiv.classList.add('disabled');
                } else {
                    if (typeof handleDateSelect === 'function') {
                        dateDiv.addEventListener('click', () => handleDateSelect(dayDate, dateDiv));
                    } else {
                        console.error("handleDateSelect function not found!");
                    }
                }

                if (selectedDate && dayDate.toDateString() === selectedDate.toDateString()) {
                    dateDiv.classList.add('selected');
                }
                calendarGridDiv.appendChild(dateDiv);
                daysAdded++;
            }
            console.log(`Added ${daysAdded} day cells.`); // DEBUG
        } catch(error) {
             console.error("Error during generateCalendar execution:", error); // DEBUG ERROR
        }
        console.log("--- generateCalendar finished ---"); // DEBUG
    }


    // --- Core Logic ---

    async function handleDateSelect(date, divElement) {
        if (!date || !(date instanceof Date) || divElement.classList.contains('disabled')) {
            console.log("handleDateSelect ignored: Invalid date or disabled.", date);
            return;
        }

        selectedDate = date;
        const currentSelectedDateISO = formatDateISO(selectedDate);
        if (!currentSelectedDateISO) {
             alert("Error: Could not format selected date.");
             return;
        }
        console.log(`handleDateSelect called for: ${currentSelectedDateISO}`); // DEBUG

        document.querySelectorAll('.calendar-day.selected').forEach(d => d.classList.remove('selected'));
        divElement.classList.add('selected');

        updateSelectedDateDisplay(); // Update text display first
        clearTimeSlotsDisplay();
        loadingMessage.style.display = 'block';
        saveScheduleButton.disabled = true;
        deleteScheduleButton.disabled = true;

        try {
            // Initialize with defaults
            currentDaySlots = {};
            Object.values(defaultTimeSlots).flat().forEach(time => {
                currentDaySlots[time] = { saved: false, selected: false };
            });
            console.log("Initialized with default slots."); // DEBUG

            // Fetch saved slots
            const fetchedSlots = await fetchScheduleForDate(currentSelectedDateISO);
            console.log(`Fetched ${fetchedSlots.length} saved slots.`); // DEBUG

            // Merge fetched into defaults
            fetchedSlots.forEach(slot => {
                 // Ensure start_time exists on the fetched slot object
                 if (slot && slot.start_time) {
                      currentDaySlots[slot.start_time] = { saved: true, selected: true };
                 } else {
                      console.warn("Fetched slot missing start_time:", slot);
                 }
            });

            // Populate UI
            populateAllTimeSlots();
            console.log("Populated all time slots based on merged state."); // DEBUG

        } catch (error) {
            // Error already logged in fetchScheduleForDate if it's a fetch error
            console.error(`Error processing schedule for ${currentSelectedDateISO}:`, error); // Log with correct date
            const authError = error.message.includes("Authentication error");
            alert(`Failed to load schedule for ${currentSelectedDateISO}. ${authError ? error.message : 'Please check connection or try again.'}`);
            currentDaySlots = {};
            populateAllTimeSlots(); // Show defaults on error
        } finally {
            loadingMessage.style.display = 'none';
            updateButtonStates();
            updateSelectedSlotsDisplay(); // Update summary based on initial state
            console.log(`handleDateSelect finished for ${currentSelectedDateISO}.`); // DEBUG
        }
    }

    function populateAllTimeSlots() {
        Object.values(timeSlotDivs).forEach(div => { if(div) div.innerHTML = ''; });
        const allTimes = Object.keys(currentDaySlots).sort(compareTimes);
        // console.log("Populating slots for times:", allTimes); // DEBUG Frequent Log
        allTimes.forEach(time24 => {
            const section = determineTimeSection(time24);
            if (section && timeSlotDivs[section]) {
                createTimeSlotButton(time24, timeSlotDivs[section]);
            } else if (!section) {
                 console.warn(`No section found for time ${time24} during population.`);
            }
        });
        Object.values(timeSlotDivs).forEach(sortButtonsInSection);
        // console.log("Finished populating slots."); // DEBUG Frequent Log
    }

    function createTimeSlotButton(time24, containerDiv) {
        if (!containerDiv) return; // Safety check
        const button = document.createElement('button');
        button.textContent = convertTo12Hour(time24);
        button.dataset.time = time24;
        const slotState = currentDaySlots[time24];
        if (!slotState) return; // Should not happen if called from populateAllTimeSlots

        if (slotState.saved) button.classList.add('saved');
        if (slotState.selected) button.classList.add('selected');
        button.addEventListener('click', () => handleTimeSlotToggle(time24, button));
        containerDiv.appendChild(button);
    }

    function handleTimeSlotToggle(time24, button) {
        if (!selectedDate || !currentDaySlots[time24]) return;
        currentDaySlots[time24].selected = !currentDaySlots[time24].selected;
        button.classList.toggle('selected', currentDaySlots[time24].selected);
        updateSelectedSlotsDisplay();
        // console.log(`Toggled ${time24} to selected: ${currentDaySlots[time24].selected}`); // DEBUG Frequent log
    }

    function handleAddTimeslot() {
        if (!selectedDate) { alert("Please select a date first."); return; }
        const hour = parseInt(hourInput.value);
        const minute = parseInt(minuteInput.value);
        const ampm = ampmSelect.value;

        if (isNaN(hour) || isNaN(minute) || hour < 1 || hour > 12 || minute < 0 || minute > 59) {
            alert("Invalid time input."); return;
        }

        let hour24 = (ampm === "PM" && hour !== 12) ? hour + 12 : (ampm === "AM" && hour === 12) ? 0 : hour;
        const minuteStr = String(minute).padStart(2, '0');
        const time24 = `${String(hour24).padStart(2, '0')}:${minuteStr}`;
        const section = determineTimeSection(time24);

        if (!section || !timeSlotDivs[section]) {
            alert("Error adding time slot: Invalid time section."); return;
        }
        const containerDiv = timeSlotDivs[section];

        // Check if slot already exists visually/in state
        if (currentDaySlots[time24]) {
            if (!currentDaySlots[time24].selected) {
                currentDaySlots[time24].selected = true;
                const existingButton = containerDiv.querySelector(`button[data-time="${time24}"]`);
                if (existingButton) existingButton.classList.add('selected');
                updateSelectedSlotsDisplay();
                alert(`Time slot ${convertTo12Hour(time24)} already existed and has been selected.`);
            } else {
                alert(`Time slot ${convertTo12Hour(time24)} already exists and is selected.`);
            }
            return;
        }

        // Add new slot
        console.log(`Adding new slot via button: ${time24}`); // DEBUG
        currentDaySlots[time24] = { saved: false, selected: true };
        createTimeSlotButton(time24, containerDiv);
        sortButtonsInSection(containerDiv);
        updateSelectedSlotsDisplay();
    }

    // --- Backend Interaction (Using JWT Authorization Header) ---

    async function fetchScheduleForDate(dateISO) {
        const apiUrl = `${API_BASE_URL}/schedule?date=${dateISO}`;
        const token = getAuthToken();
        console.log(`--- Preparing fetchScheduleForDate for ${dateISO} ---`);
        console.log("Token retrieved:", token ? "Yes" : "No");

        if (!token) {
            console.error("fetchScheduleForDate: No token found.");
            throw new Error("Authentication error: No token found. Please log in again.");
        }

        const fetchOptions = {
            method: 'GET',
            headers: {
                'Accept': 'application/json',
                'Authorization': `Bearer ${token}`
            }
        };
        console.log("Fetch options for GET /schedule:", fetchOptions);

        try {
            const response = await fetch(apiUrl, fetchOptions);
            // Log response status immediately
            console.log(`GET /schedule?date=${dateISO} response status: ${response.status}`); // DEBUG
            if (!response.ok) {
                const status = response.status;
                const statusText = response.statusText;
                let errorDetail = statusText;
                try { // Try to get more detail from body
                    const errorData = await response.json();
                    errorDetail = errorData.detail || errorDetail;
                } catch(e) { /* Ignore if body isn't JSON */ }

                if (status === 401 || status === 403) {
                    localStorage.removeItem('accessToken');
                    console.error(`Authentication error (${status}) fetching schedule.`); // DEBUG ERROR
                    throw new Error(`Authentication error (${status}): ${errorDetail}. Please log in again.`);
                }
                if (status === 404) {
                     console.log(`No schedule found via API for ${dateISO}.`); // DEBUG
                     return []; // Not an error, just empty
                 }
                console.error(`HTTP error ${status} fetching schedule: ${errorDetail}`); // DEBUG ERROR
                throw new Error(`HTTP error ${status}: ${errorDetail}`);
            }
            // Check for potentially empty but valid response (e.g., 204 No Content, though unlikely for GET)
            if (response.status === 204) return [];
            // Parse successful JSON response
            const data = await response.json();
            console.log(`Successfully fetched schedule data for ${dateISO}:`, data); // DEBUG
            return Array.isArray(data) ? data : [];
        } catch (error) {
            // Catch network errors or errors thrown above
            console.error(`Fetch/Processing error in fetchScheduleForDate for ${dateISO}:`, error);
            // Add specific message for network errors vs other errors
            if (error instanceof TypeError) { // Often indicates network issue
                 throw new Error("Network error: Could not connect to the server.");
            }
            throw error; // Re-throw other errors (like auth)
        }
    }


    async function handleSaveSchedule() {
        console.log("--- handleSaveSchedule START ---"); // DEBUG Start
    
        // Log the global 'selectedDate' value *immediately*
        const dateAtStart = selectedDate; // Capture state immediately
        console.log(">>> selectedDate at start of handleSaveSchedule:", dateAtStart ? dateAtStart.toString() : 'null'); // DEBUG
    
        const dateToSave = selectedDate; // Assign to local variable for clarity
        if (!dateToSave) {
            alert("Please select a date first."); return;
        }
    
        // Format it and log BOTH input Date and output ISO string
        const dateToSaveISO = formatDateISO(dateToSave);
        console.log(">>> Formatted dateToSaveISO:", dateToSaveISO, " (from Date:", dateToSave ? dateToSave.toString() : 'null', ")"); // DEBUG
    
        if (!dateToSaveISO) {
             alert("Error: Cannot format the selected date for saving."); return;
        }

         // --- ADD CHECK FOR SELECTED SLOTS ---
    const slotsToSave = Object.entries(currentDaySlots)
    .filter(([time, state]) => state.selected) // Filter for selected slots
    .map(([startTime, state]) => ({ start_time: startTime }));

if (slotsToSave.length === 0) {
    alert(`No time slots are selected for ${dateToSaveISO}. Please select at least one slot to save, or use Delete to clear the schedule.`);
    // Don't disable the save button here, user might want to select something
    return; // Stop the function if nothing is selected
}
// --- END CHECK ---

    
        saveScheduleButton.disabled = true;
        const token = getAuthToken();
        // Log date being used for the operation *after* formatting
        console.log(`>>> Operation target date for save: ${dateToSaveISO}`); // DEBUG
    
        if (!token) { /* ... token check ... */ }
    
        //const slotsToSave = Object.entries(currentDaySlots)
         //   .filter(([time, state]) => state.selected)
           // .map(([startTime, state]) => ({ start_time: startTime }));
    
        // Log the date being put into the request body
        const requestBody = { date: dateToSaveISO, slots: slotsToSave };
        console.log(">>> Request body for PUT:", JSON.stringify(requestBody)); // DEBUG
    
        const fetchOptions = {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify(requestBody)
        };
        // console.log("Fetch options for PUT /schedule:", fetchOptions); // Optional log
    
        const apiUrl = `${API_BASE_URL}/schedule`;
        try {
            const response = await fetch(apiUrl, fetchOptions);
            console.log(`PUT /schedule response status: ${response.status}`);
            const responseData = await response.json();
    
            if (!response.ok) {
                // Log error with the date variable we are using
                console.error(`Save failed (${response.status}) for ${dateToSaveISO}:`, responseData);
                throw new Error(responseData.detail || `Failed to save for ${dateToSaveISO} (${response.status})`);
            }
    
            // Log success with the date variable we are using
            alert(`Schedule for ${dateToSaveISO} saved successfully!`);
            console.log("Save successful:", responseData);
    
            // ... (UI update logic) ...
            Object.keys(currentDaySlots).forEach(time => { /* ... */ });
            populateAllTimeSlots();
            updateSelectedSlotsDisplay();
    
        } catch (error) {
            // Log error with the date variable we are using
            console.error(`Error saving schedule for ${dateToSaveISO}:`, error);
            alert(`Failed to save schedule for ${dateToSaveISO}: ${error.message}.`);
        } finally {
            saveScheduleButton.disabled = false;
            console.log("--- handleSaveSchedule END ---"); // DEBUG End
        }
    }


    async function handleDeleteSchedule() {
        if (!selectedDate) { alert("Please select a date first."); return; }
        const currentSelectedDateISO = formatDateISO(selectedDate);
        if (!currentSelectedDateISO) { alert("Error: Invalid date selected."); return; }
        const dateStringForAlert = selectedDate.toLocaleDateString();
        const token = getAuthToken();

        console.log(`--- Preparing handleDeleteSchedule for ${currentSelectedDateISO} ---`);
        console.log("Token retrieved:", token ? "Yes" : "No");

        if (!token) {
            alert(`Authentication error deleting for ${dateStringForAlert}. No token. Please log in.`);
            return;
        }
        if (!confirm(`Are you sure you want to delete the entire schedule for ${dateStringForAlert}?`)) { return; }
        deleteScheduleButton.disabled = true;

        const apiUrl = `${API_BASE_URL}/schedule?date=${currentSelectedDateISO}`;
        const fetchOptions = {
            method: 'DELETE',
            headers: { 'Authorization': `Bearer ${token}` }
        };
        console.log("Fetch options for DELETE /schedule:", fetchOptions);

        try {
            const response = await fetch(apiUrl, fetchOptions);
            console.log(`DELETE /schedule?date=... response status: ${response.status}`); // DEBUG
            const responseData = await response.json(); // Assume JSON response

            if (!response.ok) {
                if (response.status === 401 || response.status === 403) localStorage.removeItem('accessToken');
                console.error(`Delete failed (${response.status}):`, responseData); // DEBUG ERROR
                throw new Error(responseData.detail || `Failed to delete (${response.status})`);
            }

            alert(`Schedule for ${dateStringForAlert} deleted successfully.`);
            console.log("Delete successful:", responseData); // DEBUG
            clearTimeSlotsDisplay();
            updateSelectedDateDisplay(); // Update summary display too

        } catch (error) {
            console.error(`Error deleting schedule for ${currentSelectedDateISO}:`, error);
            alert(`Failed to delete schedule for ${dateStringForAlert}: ${error.message}.`);
        } finally {
            deleteScheduleButton.disabled = false;
        }
    }

}); // End DOMContentLoaded