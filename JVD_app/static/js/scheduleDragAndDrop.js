document.addEventListener('DOMContentLoaded', function() {
    initDragAndDrop();
    fetchAndRenderSchedule();
});

let drake = null;

function initDragAndDrop() {
    if (drake) {
        console.log('Destroying existing drake instance.');
        drake.destroy();
        drake = null;
    }

    const employeeList = document.getElementById('employees-list');
    const dropzones = Array.from(document.querySelectorAll('.dropzone'));
    console.log(`Found ${dropzones.length} dropzones for initialization.`);

    if (!employeeList || dropzones.length === 0) {
        console.error('Drag and drop initialization aborted: Required elements not found.');
        return;
    }

    const containers = [employeeList].concat(dropzones);
  
    drake = dragula(containers, {
        copy: (el, source) => source === employeeList,
        accepts: (el, target) => target !== employeeList && !target.classList.contains('employee-block'),
        removeOnSpill: false,
        revertOnSpill: true,
        mirrorContainer: document.body,
        moves: (el) => {
            el.classList.add('employee-block'); // Ensure the mirror gets the correct class
            return true;
        }
    });

    drake.on('drop', function(el, target, source) {
        if (target === employeeList) return;
    
        const employeeId = el.getAttribute('data-employee-id');
        const date = target.getAttribute('data-date');
        const shiftTypeId = target.getAttribute('data-shift-type-id');
        const group = el.getAttribute('data-group');
    
        let action = source !== employeeList && source.classList.contains('dropzone') ? 'move' : 'add';
        let originalDate = action === 'move' ? source.getAttribute('data-date') : date;
        let originalShiftTypeId = action === 'move' ? source.getAttribute('data-shift-type-id') : shiftTypeId;
    
        // Set the element ID
        const elementId = `employee-block-${employeeId}-${date}-${shiftTypeId}`;
        el.setAttribute('id', elementId);
    
        // Update data attributes
        el.setAttribute('data-date', date);
        el.setAttribute('data-shift-type-id', shiftTypeId);
    
        // Add buttons
        addButtonsToEmployeeBlock(el);
    
        updateSchedule(employeeId, shiftTypeId, date, action, originalDate, originalShiftTypeId);
    
        if (source === employeeList) {
            let clonedEl = el.cloneNode(true);
            clonedEl.setAttribute('id', elementId); // Set the ID on the cloned element
            clonedEl.setAttribute('data-shift-type-id', shiftTypeId);
            clonedEl.setAttribute('data-date', date); // Ensure date is set on clone
            clonedEl.setAttribute('data-group', group); // Ensure group is set on clone
            clonedEl.classList.add(`group-${group}`);
            target.appendChild(clonedEl);
            drake.containers.push(clonedEl);
        } else {
            el.setAttribute('data-shift-type-id', shiftTypeId);
            target.appendChild(el);
        }
    });

    drake.on('drag', function(el) {
        console.log('Dragging', el);
    });
    
    drake.on('dragend', function(el) {
        const shadows = document.querySelectorAll('.gu-mirror, .gu-transit');
        shadows.forEach(shadow => shadow.remove());
    });
};

function addButtonsToEmployeeBlock(el) {
    const elementId = el.getAttribute('id');

    if (!el.querySelector('.cog-btn')) {
        const cogButton = document.createElement('button');
        cogButton.className = 'cog-btn';
        cogButton.innerHTML = '⚙️';
        cogButton.onclick = () => openOvertimeModal(
            el.getAttribute('data-employee-id'), 
            el.getAttribute('data-date'), 
            el.getAttribute('data-shift-type-id')
        );
        el.appendChild(cogButton);
    }

    if (!el.querySelector('.delete-btn')) {
        const deleteButton = document.createElement('button');
        deleteButton.className = 'delete-btn';
        deleteButton.textContent = '❌';
        deleteButton.onclick = () => {
            deleteScheduleEntry(
                el.getAttribute('data-employee-id'), 
                el.getAttribute('data-date'), 
                el.getAttribute('data-shift-type-id'), 
                el.getAttribute('id')
            );
        };
        el.appendChild(deleteButton);
    }
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
    let startDate = moment(monthStart);
    let endDate = moment(startDate).endOf('month');

    const startFormat = startDate.format('YYYY-MM-DD');
    const endFormat = endDate.format('YYYY-MM-DD');

    fetch(`/api/schedule/?week_start=${startFormat}&week_end=${endFormat}`)
    .then(response => response.json())
    .then(data => {
        document.querySelectorAll('.dropzone').forEach(dz => dz.innerHTML = ''); // Clear existing blocks
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
    })
    .catch(error => console.error('Error fetching schedule:', error));
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

    const nameSpan = document.createElement('span');
    nameSpan.className = 'employee-name';
    nameSpan.textContent = `${employee.surname} ${employee.name.charAt(0)}. (${employee.group})`;
    div.appendChild(nameSpan);

    addButtonsToEmployeeBlock(div);

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
