document.addEventListener('DOMContentLoaded', function() {
    initDragAndDrop();
});

function initDragAndDrop() {
    const employeeList = document.getElementById('employees-list');
    const dropzones = Array.from(document.querySelectorAll('.dropzone'));
    const containers = [employeeList].concat(dropzones);
  
    const drake = dragula(containers, {
        copy: (el, source) => source === employeeList,
        accepts: (el, target) => target !== employeeList && !target.classList.contains('employee-block'),
        removeOnSpill: false,
        revertOnSpill: true,
        mirrorContainer: document.body,
    });
  
    const employeeAssignments = new Map();
  
    drake.on('drop', function(el, target, source, sibling) {
      if (target === employeeList) return;
  
      const employeeId = el.getAttribute('data-employee-id');
      const shiftTypeId = target.getAttribute('data-shift-type-id');
      const date = target.getAttribute('data-date');
      let action = source !== employeeList && source.classList.contains('dropzone') ? 'move' : 'add';
  
      updateSchedule(employeeId, shiftTypeId, date, action);
  
      if (source === employeeList) {
        let clonedEl = el.cloneNode(true);
        clonedEl.classList.add('hide-counter');
        target.appendChild(clonedEl);
        drake.containers.push(clonedEl);
      } else {
        target.appendChild(el);
      }
  
      let count = employeeAssignments.get(employeeId) || 0;
      count = action === 'add' ? ++count : count;
      employeeAssignments.set(employeeId, count);
      updateEmployeeBlockCounter(employeeId, count);
    });
  

  function updateSchedule(employeeId, shiftTypeId, date, action) {
    // Modify the URL to include the action as a query parameter
    const url = `/update_schedule/?action=${action}`;

    fetch(url, { // Make sure to use the modified URL with action
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken'),
        },
        body: JSON.stringify({ employeeId, shiftTypeId, date }),
    })
    .then(response => response.json())
    .then(data => {
        console.log('Success:', data);
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
              if (cookie.substring(0, name.length + 1) === (name + '='))
                  cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                  break;
          }
      }
      return cookieValue;
  }

  function incrementAssignments(employeeId) {
      let count = employeeAssignments.get(employeeId) || 0;
      count++;
      employeeAssignments.set(employeeId, count);
      return count;
  }

  function updateEmployeeBlockCounter(employeeId, count) {
    const employeeBlock = employeeList.querySelector(`[data-employee-id="${employeeId}"]`);
    if (!employeeBlock) {
        console.error(`Employee block not found for employeeId: ${employeeId}`);
        return; // Exit the function if no employeeBlock is found
    }
    let counter = employeeBlock.querySelector('.drop-counter');
    if (!counter) {
        counter = document.createElement('span');
        counter.className = 'drop-counter';
        employeeBlock.appendChild(counter);
    }
    counter.innerText = count; // Display count without "/7"
}

  drake.on('dragend', function(el) {
      const shadows = document.querySelectorAll('.gu-mirror, .gu-transit');
      shadows.forEach(shadow => shadow.remove());
  });

  // New functionality to fetch and render schedule on page load
  fetchAndRenderSchedule();
};

// Function to fetch schedule data and update the UI accordingly
function fetchAndRenderSchedule() {
  fetch('/api/schedule/')
  .then(response => response.json())
  .then(data => {
      data.forEach(({ date, shift_type_id, employees }) => {
          const cell = document.querySelector(`.dropzone[data-shift-type-id="${shift_type_id}"][data-date="${date}"]`);
          employees.forEach(employee => {
              const employeeBlock = createEmployeeBlock(employee);
              cell.appendChild(employeeBlock);
          });
      });
  })
  .catch(error => console.error('Error fetching schedule:', error));
}

function updateSchedule(employeeId, shiftTypeId, date, action) {
    const url = `/update_schedule/`;
    // Construct the request body including the action parameter
    const requestBody = JSON.stringify({ employeeId, shiftTypeId, date, action });
    console.log("Sending request with body:", requestBody); // Logging the request body to debug

    fetch(url, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken'), // Ensure CSRF token is correctly fetched and included
        },
        body: requestBody, // Use the requestBody that includes the action
    })
    .then(response => {
        if (!response.ok) {
            throw new Error('Network response was not ok: ' + response.statusText);
        }
        return response.json();
    })
    .then(data => {
        console.log('Success:', data); // Logging the success response
    })
    .catch(error => {
        console.error('Error:', error); // Logging any error that occurs during the fetch operation
    });
}
  

function createEmployeeBlock(employee) {
  const div = document.createElement('div');
  div.className = 'employee-block';
  div.setAttribute('data-employee-id', employee.id);
  div.textContent = employee.name; // Adjust as needed
  return div;
}
