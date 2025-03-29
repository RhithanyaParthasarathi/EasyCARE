document.addEventListener('DOMContentLoaded', function() {
    const currentMonthSpan = document.getElementById('current-month');
    const calendarGridDiv = document.getElementById('calendar-grid');
    const prevMonthButton = document.getElementById('prev-month');
    const nextMonthButton = document.getElementById('next-month');
    const morningSlotsDiv = document.querySelector('.time-slots.morning');
    const afternoonSlotsDiv = document.querySelector('.time-slots.afternoon');
    const eveningSlotsDiv = document.querySelector('.time-slots.evening');
    const nightSlotsDiv = document.querySelector('.time-slots.night');
    const hourInput = document.getElementById('hourInput');
    const minuteInput = document.getElementById('minuteInput');
    const ampmSelect = document.getElementById('ampmSelect');
    const addTimeslotButton = document.getElementById('addTimeslotButton');
    const selectedDateDisplay = document.getElementById('selected-date-display');
    const selectedSlotsDisplay = document.getElementById('selected-slots-display');

    let currentDate = new Date();
    let selectedDate = null; // Track the selected date
    let selectedTimeSlots = {}; // Object to store selected time slots for each date

    let morningTimeSlots = ["08:00", "08:30", "09:00", "09:30", "10:00", "10:30", "11:00", "11:30"]; // 24-hour format
    let afternoonTimeSlots = ["12:00", "12:30", "13:00", "13:30", "14:00", "14:30", "15:00", "15:30"]; // 24-hour format
    let eveningTimeSlots = ["16:00", "16:30", "17:00", "17:30", "18:00", "18:30", "19:00", "19:30"]; // 24-hour format
    let nightTimeSlots = ["20:00", "20:30", "21:00", "21:30", "22:00", "22:30", "23:00", "23:30"]; // 24-hour format

    function generateCalendar(year, month) {
        const firstDay = new Date(year, month, 1);
        const lastDay = new Date(year, month + 1, 0);
        const daysInMonth = lastDay.getDate();
        const startingDay = firstDay.getDay();

        currentMonthSpan.textContent = new Date(year, month).toLocaleString('default', { month: 'long' }) + ' ' + year;
        calendarGridDiv.innerHTML = '';

        // Add empty boxes for the days before the first day of the month
        for (let i = 0; i < startingDay; i++) {
            const emptyDiv = document.createElement('div');
            emptyDiv.classList.add('calendar-day', 'empty');
            calendarGridDiv.appendChild(emptyDiv);
        }

        // Add dates to the calendar
        for (let i = 1; i <= daysInMonth; i++) {
            const dateDiv = document.createElement('div');
            dateDiv.classList.add('calendar-day');
            dateDiv.textContent = i;
            calendarGridDiv.appendChild(dateDiv);

            dateDiv.addEventListener('click', function() {
                selectedDate = new Date(year, month, i);
                updateSelectedDateDisplay(); // Update the display

                const calendarDays = document.querySelectorAll('.calendar-day');
                calendarDays.forEach(day => day.classList.remove('selected'));
                dateDiv.classList.add('selected');

             //Make sure when Date are clicked timeslots are available
                populateTimeSlots(morningTimeSlots, morningSlotsDiv, 'morning');
                populateTimeSlots(afternoonTimeSlots, afternoonSlotsDiv, 'afternoon');
                populateTimeSlots(eveningTimeSlots, eveningSlotsDiv, 'evening');
                populateTimeSlots(nightTimeSlots, nightSlotsDiv, 'night');
            });

             // Highlight the selected date if it matches the current day being rendered
            if (selectedDate && selectedDate.getFullYear() === year && selectedDate.getMonth() === month && selectedDate.getDate() === i) {
                dateDiv.classList.add('selected');
            }
        }

        updateSelectedDateDisplay();
    }

    function populateTimeSlots(timeslotList, slotsDiv, section) {
        slotsDiv.innerHTML = '';

        timeslotList.forEach(timeslot => {
            const button = document.createElement('button');
            button.textContent = convertTo12Hour(timeslot); // Use the helper function
            button.dataset.time = timeslot; // Store 24-hour time for easier processing

            if (selectedDate && selectedTimeSlots[selectedDate.toDateString()] && selectedTimeSlots[selectedDate.toDateString()][section] && selectedTimeSlots[selectedDate.toDateString()][section].includes(timeslot)) {
                button.classList.add('selected');
            }

            button.addEventListener('click', () => {
                if (!selectedDate) {
                    alert("Please select a date first.");
                    return;
                }

                const dateString = selectedDate.toDateString();

                if (!selectedTimeSlots[dateString]) {
                    selectedTimeSlots[dateString] = {};
                }

                if (!selectedTimeSlots[dateString][section]) {
                    selectedTimeSlots[dateString][section] = [];
                }

                if (button.classList.contains('selected')) {
                    button.classList.remove('selected');
                    selectedTimeSlots[dateString][section] = selectedTimeSlots[dateString][section].filter(time => time !== timeslot);
                } else {
                    button.classList.add('selected');
                    selectedTimeSlots[dateString][section].push(timeslot);
                }

                updateSelectedSlotsDisplay();
            });
            slotsDiv.appendChild(button);
        });
    }

    addTimeslotButton.addEventListener('click', () => {
         //If the selected Calendar is null show error
        if (selectedDate == null) {
            alert("Select a date first!");
            return;
        }

        const hour = parseInt(hourInput.value);
        const minute = parseInt(minuteInput.value);
        const ampm = ampmSelect.value;

        if (isNaN(hour) || isNaN(minute) || hour < 1 || hour > 12 || minute < 0 || minute > 59) {
            alert("Invalid time input.");
            return;
        }

        const hour24 = (ampm === "PM" && hour !== 12) ? hour + 12 : (ampm === "AM" && hour === 12) ? 0 : hour;
        const time24 = `${String(hour24).padStart(2, '0')}:${String(minute).padStart(2, '0')}`;

        let section = determineTimeSection(time24);

        if (section) {
            let targetTimeSlots;
            let targetSlotsDiv;

            switch (section) {
                case 'morning':
                    targetTimeSlots = morningTimeSlots;
                    targetSlotsDiv = morningSlotsDiv;
                    break;
                case 'afternoon':
                    targetTimeSlots = afternoonTimeSlots;
                    targetSlotsDiv = afternoonSlotsDiv;
                    break;
                case 'evening':
                    targetTimeSlots = eveningTimeSlots;
                    targetSlotsDiv = eveningSlotsDiv;
                    break;
                case 'night':
                    targetTimeSlots = nightTimeSlots;
                    targetSlotsDiv = nightSlotsDiv;
                    break;
                default:
                    console.error("Error determining time sections");
                    return;
            }

            if (!targetTimeSlots.includes(time24)) {
                targetTimeSlots.push(time24);
                populateTimeSlots(targetTimeSlots, targetSlotsDiv, section);
            } else {
                alert("Time slot already exists.");
            }

        } else {
            alert("Error determining time section.");
        }
    });

     // Helper function to determine time section based on time
    function determineTimeSection(time) {
        const [hours] = time.split(':');
        const hour = parseInt(hours);

        if (hour >= 6 && hour < 12) {
            return 'morning';
        } else if (hour >= 12 && hour < 17) {
            return 'afternoon';
        } else if (hour >= 17 && hour < 22) {
            return 'evening';
        } else if (hour >= 22 || hour < 6) {
            return 'night';
        }
        return null;
    }

    function updateSelectedDateDisplay() {
        if (selectedDate) {
            selectedDateDisplay.textContent = selectedDate.toLocaleDateString();
        } else {
            selectedDateDisplay.textContent = "No date selected";
        }
        updateSelectedSlotsDisplay();
    }

    function updateSelectedSlotsDisplay() {
        selectedSlotsDisplay.innerHTML = '';
        if (selectedDate && selectedTimeSlots[selectedDate.toDateString()]) {
            const dateString = selectedDate.toDateString();

            for (const section in selectedTimeSlots[dateString]) {
                if (selectedTimeSlots[dateString].hasOwnProperty(section)) {
                    const timeslots = selectedTimeSlots[dateString][section];

                    if (timeslots.length > 0) {
                        const sectionHeader = document.createElement('h5');
                        sectionHeader.textContent = section.charAt(0).toUpperCase() + section.slice(1); // Capitalize section name
                        selectedSlotsDisplay.appendChild(sectionHeader);

                        const timeList = document.createElement('ul');
                        timeslots.forEach(timeslot => {
                            const timeItem = document.createElement('li');
                            timeItem.textContent = convertTo12Hour(timeslot);
                            timeList.appendChild(timeItem);
                        });
                        selectedSlotsDisplay.appendChild(timeList);
                    }
                }
            }

        } else {
            selectedSlotsDisplay.textContent = "No time slots selected for this date.";
        }
    }

    // Helper function to convert 24-hour format to 12-hour format
    function convertTo12Hour(time24) {
        const [hours, minutes] = time24.split(':');
        let hoursInt = parseInt(hours);
        const ampm = hoursInt >= 12 ? 'PM' : 'AM';
        hoursInt = hoursInt % 12;
        hoursInt = hoursInt ? hoursInt : 12; // the hour '0' should be '12'
        return hoursInt + ':' + minutes + ' ' + ampm;
    }

    // Initial calendar generation
    generateCalendar(currentDate.getFullYear(), currentDate.getMonth());
});