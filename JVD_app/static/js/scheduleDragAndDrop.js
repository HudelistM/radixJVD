document.addEventListener('alpine:init', () => {
    console.log('Alpine initialized');
    console.log('Attaching scheduleManager store');

    Alpine.store('scheduleManager', {
        selectedRow: null,
        featureToggle: false,

        selectRow(index) {
            console.log('Selecting row:', index);
            if (!this.featureToggle) {
                console.log('Feature toggle is off');
                return;
            }

            if (this.selectedRow === index) {
                this.selectedRow = null;
            } else {
                this.selectedRow = index;
            }
            this.updateEmployeeLock();
        },

        updateEmployeeLock() {
            console.log('Updating employee lock status');
            
            // Unlock all employee blocks in both the list and schedule
            document.querySelectorAll('.employee-block').forEach(block => {
                block.classList.remove('employee-locked');
                block.setAttribute('draggable', 'true');
            });
        
            if (!this.featureToggle || this.selectedRow === null) return;
        
            // Get selected row (schedule table row)
            const selectedRow = document.querySelectorAll('tbody tr')[this.selectedRow];
            let employeeCount = {};
        
            // Mark employees that are already assigned in the selected row
            selectedRow.querySelectorAll('.employee-block').forEach(block => {
                const employeeId = block.getAttribute('data-employee-id');
                employeeCount[employeeId] = (employeeCount[employeeId] || 0) + 1;
            });
        
            // Lock employees both in the list and in the schedule table
            document.querySelectorAll('.employee-block').forEach(block => {
                const employeeId = block.getAttribute('data-employee-id');
                if (employeeCount[employeeId]) {
                    block.classList.add('employee-locked');
                    block.setAttribute('draggable', 'false');
                }
            });
        },
        

        setFeatureToggle(isChecked) {
            console.log('Feature toggled:', isChecked);
            this.featureToggle = isChecked;
            this.updateEmployeeLock();
        }
    });
});

// Function to initialize feature toggle checkbox listener
function initializeFeatureToggle() {
    const toggle = document.getElementById('employee-lock-toggle');

    // Remove any previous event listener to avoid duplication
    toggle.removeEventListener('change', toggleHandler);  // Ensure no duplicate listeners
    toggle.addEventListener('change', toggleHandler);  // Attach a single listener
}

// Separate the event handler to make it reusable
function toggleHandler(event) {
    const isChecked = event.target.checked;
    console.log('Toggling feature: ', isChecked);  // Log when toggle is clicked
    Alpine.store('scheduleManager').setFeatureToggle(isChecked);
}

function reinitializeComponents() {
    initDragAndDrop();
    attachRightClickEventListeners();
    
    // Only initialize the feature toggle once (calling removeEventListener to ensure no duplicates)
    initializeFeatureToggle();
    
    Alpine.store('scheduleManager').updateEmployeeLock();
}

// Call this once DOM is fully loaded
document.addEventListener('DOMContentLoaded', function() {
    initializeFeatureToggle();  // Initialize the feature toggle

    // Fetch and render the schedule grid
    fetchAndRenderSchedule();

    // Initialize drag and drop functionality
    initDragAndDrop();

    // Setup month navigation and other event listeners
    populateMonthDropdown();
    setupMonthNavigation();
    attachRightClickEventListeners();
});

let drake = null;

function initDragAndDrop() {
    if (drake) {
        console.log('Destroying existing drake instance.');
        drake.destroy();
        drake = null;
    }

    const employeeContainers = Array.from(document.querySelectorAll('.group-container'));
    const dropzones = Array.from(document.querySelectorAll('.dropzone'));
    const deleteZone = document.getElementById('delete-zone');

    console.log(`Found ${dropzones.length} dropzones and ${employeeContainers.length} employee containers for initialization.`);
    console.log(`Delete zone found: ${deleteZone ? 'Yes' : 'No'}`);

    if (employeeContainers.length === 0 || dropzones.length === 0 || !deleteZone) {
        console.error('Drag and drop initialization aborted: Required elements not found.');
        return;
    }

    const containers = employeeContainers.concat(dropzones, [deleteZone]);

    drake = dragula(containers, {
        copy: (el, source) => el.classList.contains('employee-block') && employeeContainers.includes(source),
        accepts: (el, target) => target.classList.contains('dropzone') || target === deleteZone,
        removeOnSpill: false,
        revertOnSpill: true,
        mirrorContainer: document.body,
        moves: (el) => {
            // Prevent dragging locked employees
            return !el.classList.contains('employee-locked') && el.classList.contains('employee-block');
        }
    });

    drake.on('drop', function(el, target, source) {
        if (!target) return;

        const employeeId = el.getAttribute('data-employee-id');
        let date = target.getAttribute('data-date');
        let shiftTypeId = target.getAttribute('data-shift-type-id');
        const group = el.getAttribute('data-group');

        // Check if the target is the delete zone
        if (target === deleteZone) {
            if (!date) date = source.getAttribute('data-date');
            if (!shiftTypeId) shiftTypeId = source.getAttribute('data-shift-type-id');
            const elementId = el.getAttribute('id');
            deleteScheduleEntry(employeeId, date, shiftTypeId, elementId);
            el.remove();
            return;
        }

        // Proceed with the regular drop logic
        let action = !employeeContainers.includes(source) && source.classList.contains('dropzone') ? 'move' : 'add';
        let originalDate = action === 'move' ? source.getAttribute('data-date') : date;
        let originalShiftTypeId = action === 'move' ? source.getAttribute('data-shift-type-id') : shiftTypeId;

        // Set the element ID
        const elementId = `employee-block-${employeeId}-${date}-${shiftTypeId}`;
        el.setAttribute('id', elementId);

        // Update data attributes
        el.setAttribute('data-date', date);
        el.setAttribute('data-shift-type-id', shiftTypeId);

        updateSchedule(employeeId, shiftTypeId, date, action, originalDate, originalShiftTypeId);

        if (employeeContainers.includes(source)) {
            let clonedEl = el.cloneNode(true);
            clonedEl.setAttribute('id', elementId); // Set the ID on the cloned element
            clonedEl.setAttribute('data-shift-type-id', shiftTypeId);
            clonedEl.setAttribute('data-date', date); // Ensure date is set on clone
            clonedEl.setAttribute('data-group', group); // Ensure group is set on clone
            clonedEl.classList.add(`group-${group}`);
            target.appendChild(clonedEl);
        } else {
            el.setAttribute('data-shift-type-id', shiftTypeId);
            target.appendChild(el);
        }

        Alpine.store('scheduleManager').updateEmployeeLock();
        // Reattach right-click event listener after drop
        attachRightClickEventListeners();
    });

    drake.on('drag', function(el) {
        console.log('Dragging', el);
    });

    drake.on('dragend', function(el) {
        const shadows = document.querySelectorAll('.gu-mirror, .gu-transit');
        shadows.forEach(shadow => shadow.remove());
    });

    drake.on('over', function(el, container) {
        if (container === deleteZone) {
            container.classList.add('bg-red-500');
        }
    });

    drake.on('out', function(el, container) {
        if (container === deleteZone) {
            container.classList.remove('bg-red-500');
        }
    });
}

function updateSchedule(employeeId, shiftTypeId, date, action, originalDate, originalShiftTypeId) {
    const url = `/update_schedule/`;
    const requestBody = JSON.stringify({
        employeeId: employeeId,
        shiftTypeId: shiftTypeId,
        date: date,
        action: action,
        originalDate: originalDate,
        originalShiftTypeId: originalShiftTypeId
    });

    console.log("Sending request with body:", requestBody);

    fetch(url, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken')
        },
        body: requestBody,
    })
    .then(response => {
        if (!response.ok) {
            throw new Error('Network response was not ok: ' + response.statusText);
        }
        return response.json();
    })
    .then(data => {
        console.log('Success:', data);
    })
    .catch(error => {
        console.error('Error:', error);
    });
}

function fetchAndRenderSchedule() {
    let monthStart = document.getElementById('schedule-grid').getAttribute('data-month-start');
    console.log('MonthStart:', monthStart); // Confirming the month start

    let startDate = moment(monthStart).startOf('month');
    let endDate = moment(monthStart).endOf('month');

    const startFormat = startDate.format('YYYY-MM-DD');
    const endFormat = endDate.format('YYYY-MM-DD');

    fetch(`/schedule/?month_start=${monthStart}`, {
        headers: {
            'X-Requested-With': 'XMLHttpRequest'  // Important for Django to recognize this as an AJAX request
        }
    })
    .then(response => response.text())  // Expect HTML in response
    .then(html => {
        document.getElementById('schedule-grid').innerHTML = html;

        // After HTML is updated, fetch JSON data
        return fetch(`/api/schedule/?month_start=${startFormat}&month_end=${endFormat}`);
    })
    .then(response => response.json()) // Process JSON response
    .then(data => {
        updateScheduleGrid(data);
        reinitializeComponents(); 
    })
    .catch(error => console.error('Error during fetch operations:', error));
}

function updateScheduleGrid(data) {
    document.querySelectorAll('.dropzone').forEach(dz => dz.innerHTML = '');
    data.forEach(({ date, shift_type_id, employees }) => {
        const cell = document.querySelector(`.dropzone[data-shift-type-id="${shift_type_id}"][data-date="${date}"]`);
        if (!cell) {
            console.error('Dropzone not found for date:', date, 'and shift type ID:', shift_type_id);
            return;
        }
        employees.forEach(employee => {
            const employeeBlock = createEmployeeBlock(employee, date, shift_type_id);
            cell.appendChild(employeeBlock);
        });
    });
    console.log('Schedule fetched and rendered successfully.');

    // Reattach right-click event listener after updating the schedule grid
    attachRightClickEventListeners();
}

function createEmployeeBlock(employee, date, shiftTypeId) {
    const div = document.createElement('div');
    const elementId = `employee-block-${employee.id}-${date}-${shiftTypeId}`;
    div.className = `employee-block group-${employee.group}`;
    div.setAttribute('id', elementId);
    div.setAttribute('data-employee-id', employee.id);
    div.setAttribute('data-group', employee.group);
    div.setAttribute('data-shift-type-id', shiftTypeId);
    div.setAttribute('data-date', date);

    // Single span for role number and name
    const nameSpan = document.createElement('span');
    nameSpan.className = 'employee-name';
    nameSpan.textContent = `(${employee.role_number}) ${employee.surname} ${employee.name.charAt(0)}.`; // Concatenated role_number, surname, and name
    div.appendChild(nameSpan);

    return div;
}



function openOvertimeModal(employeeId, date, shiftTypeId) {
    console.log(`Opening modal for Employee ID: ${employeeId}, Date: ${date}, Shift Type ID: ${shiftTypeId}`);

    let employeeInput = document.getElementById('employee-id');
    let dateInput = document.getElementById('work-date');
    let shiftTypeInput = document.getElementById('shift-type-id');
    let modal = document.getElementById('overtime-dialog');

    employeeInput.value = employeeId;
    dateInput.value = date;
    shiftTypeInput.value = shiftTypeId;

    fetch(`/get_workday_data/?employee_id=${employeeId}&date=${date}&shift_type_id=${shiftTypeId}`)
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            document.getElementById('overtime-hours').value = data.data.overtime_hours || 0;
            document.getElementById('overtime-hours-service').value = data.data.overtime_service || 0;
            document.getElementById('day-hours').value = data.data.day_hours || 0;
            document.getElementById('night-hours').value = data.data.night_hours || 0;
        } else {
            console.error('Failed to fetch workday data:', data);
            throw new Error('Failed to fetch data');
        }
        modal.classList.remove('hidden');
    })
    .catch(error => {
        console.error('Error fetching workday data:', error);
        modal.classList.remove('hidden');
    });
}

function closeOvertimeDialog() {
    console.log('Closing modal');
    document.getElementById('overtime-dialog').classList.add('hidden');
}

function submitOvertime() {
    const employeeId = document.getElementById('employee-id').value;
    const date = document.getElementById('work-date').value;
    const shiftTypeId = document.getElementById('shift-type-id').value;
    const overtimeHours = document.getElementById('overtime-hours').value;
    const overtimeHoursService = document.getElementById('overtime-hours-service').value;
    const dayHours = document.getElementById('day-hours').value;
    const nightHours = document.getElementById('night-hours').value;

    let requestData = { employee_id: employeeId, date: date, shift_type_id: shiftTypeId };
    
    if (overtimeHours !== '') {
        requestData.overtime_hours = parseFloat(overtimeHours);
    }
    if (overtimeHoursService !== '') {
        requestData.overtime_service = parseFloat(overtimeHoursService);
    }
    if (dayHours !== '') {
        requestData.day_hours = parseFloat(dayHours);
    }
    if (nightHours !== '') {
        requestData.night_hours = parseFloat(nightHours);
    }

    console.log("Submitting overtime with data:", requestData);

    fetch('/update_overtime_hours/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken')
        },
        body: JSON.stringify(requestData)
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            closeOvertimeDialog();
        } else {
            console.error(data.error);
        }
    })
    .catch(error => {
        console.error('Error:', error);
    });
}

function deleteScheduleEntry(employeeId, date, shiftTypeId, elementId) {
    const url = '/delete_workday/';
    const requestBody = JSON.stringify({
        employee_id: employeeId,
        date: date,
        shift_type_id: shiftTypeId
    });

    console.log(`Attempting to delete employee block with ID: ${elementId}`);
    console.log(`Request body: ${requestBody}`); // Debug statement

    fetch(url, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken')
        },
        body: requestBody
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            console.log('Deletion successful:', data.message);
            const elementToRemove = document.getElementById(elementId);
            if (elementToRemove) {
                console.log('Element found:', elementToRemove);
                // Add animation class before removing
                elementToRemove.classList.add('animate-fade-out');
                // Ensure the element is fully removed after the animation
                elementToRemove.addEventListener('transitionend', () => {
                    console.log('Transition ended, removing element');
                    elementToRemove.remove();
                });
                // Fallback for browsers where transitionend might not fire
                setTimeout(() => {
                    if (document.body.contains(elementToRemove)) {
                        console.log('Fallback: removing element');
                        elementToRemove.remove();
                    }
                }, 300);
            } else {
                console.error('Element not found:', elementId);
            }
        } else {
            console.error('Deletion failed:', data.message);
        }
    })
    .catch(error => {
        console.error('Error:', error);
    });
}

function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

function changeMonth(offset) {
    const monthStart = document.getElementById('schedule-grid').getAttribute('data-month-start');
    let currentDate = moment(monthStart).add(offset, 'months');

    // Always use the first day of the new month when navigating
    const firstDayOfMonth = currentDate.startOf('month').format('YYYY-MM-DD');
    updateMonthStart(firstDayOfMonth);
}

function setupMonthNavigation() {
    const prevMonthButton = document.getElementById('prev-month');
    const nextMonthButton = document.getElementById('next-month');
    const monthSelect = document.getElementById('month-select');

    prevMonthButton.addEventListener('click', () => changeMonth(-1));
    nextMonthButton.addEventListener('click', () => changeMonth(1));
    monthSelect.addEventListener('change', (event) => {
        updateMonthStart(event.target.value);
        fetchAndRenderSchedule().then(() => {
            updateMonthSelection(); // Make sure dropdown updates after schedule is rendered
        });
    });
}

function updateMonthStart(newDate) {
    document.getElementById('schedule-grid').setAttribute('data-month-start', newDate);
    document.getElementById('month-select').value = newDate;  // Select the correct month in the dropdown
    fetchAndRenderSchedule();  // Fetch and display the schedule for the entire week coverage
}

function populateMonthDropdown() {
    const monthSelect = document.getElementById('month-select');
    monthSelect.innerHTML = ''; // Clear existing options

    // Get the current year to make sure the dropdown reflects the current and accurate year
    const currentYear = new Date().getFullYear();

    // Define Croatian month names
    const monthNames = ['Siječanj', 'Veljača', 'Ožujak', 'Travanj', 'Svibanj', 'Lipanj', 
                        'Srpanj', 'Kolovoz', 'Rujan', 'Listopad', 'Studeni', 'Prosinac'];

    // Create options for each month
    monthNames.forEach((name, index) => {
        const month = index + 1; // Month index starts from 1 (January) to 12 (December)
        const monthValue = `${currentYear}-${month.toString().padStart(2, '0')}-01`; // Format to YYYY-MM-DD
        const option = document.createElement('option');
        option.value = monthValue;
        option.textContent = `${name} ${currentYear}`;
        monthSelect.appendChild(option);
    });

    // Automatically select the current month in the dropdown
    updateMonthSelection();
}

function updateMonthSelection() {
    const currentMonthStart = document.getElementById('schedule-grid').getAttribute('data-month-start');
    const monthSelect = document.getElementById('month-select');
    
    // Check if we have the month start set, else fallback to today's month
    if (!currentMonthStart) {
        const today = new Date();
        const currentMonthFormatted = `${today.getFullYear()}-${(today.getMonth() + 1).toString().padStart(2, '0')}-01`;
        document.getElementById('schedule-grid').setAttribute('data-month-start', currentMonthFormatted);
        monthSelect.value = currentMonthFormatted;
    } else {
        monthSelect.value = currentMonthStart;
    }
}

function attachRightClickEventListeners() {
    document.querySelectorAll('.employee-block').forEach(block => {
        block.removeEventListener('contextmenu', handleContextMenu); // Remove existing listeners to avoid duplication
        block.addEventListener('contextmenu', handleContextMenu); // Attach the new listener
    });
}

function handleContextMenu(event) {
    event.preventDefault();
    const employeeId = this.getAttribute('data-employee-id');
    const date = this.getAttribute('data-date');
    const shiftTypeId = this.getAttribute('data-shift-type-id');
    openOvertimeModal(employeeId, date, shiftTypeId);
}

