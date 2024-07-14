document.addEventListener('DOMContentLoaded', () => {
    const modal = document.querySelector('.modal');
    const openModalButton = document.querySelector('.modal-open');
    const closeModalButtons = document.querySelectorAll('.modal-close');
    const editButtons = document.querySelectorAll('.edit-button');
    const deleteButtons = document.querySelectorAll('.delete-button');
    const form = document.getElementById('employee-form');
    const employeeIdInput = document.getElementById('employee-id');
    const submitButton = document.querySelector('.modal-add');
    const successMessage = document.getElementById('success-message');

    // Open modal for adding a new employee
    openModalButton.addEventListener('click', () => {
        form.reset();
        employeeIdInput.value = '';
        document.getElementById('modal-title').textContent = 'Dodaj novog radnika';
        submitButton.textContent = 'Dodaj';
        modal.classList.remove('hidden', 'opacity-0', 'pointer-events-none');
    });

    // Open modal for editing an existing employee
    editButtons.forEach(button => {
        button.addEventListener('click', function() {
            const employeeId = this.getAttribute('data-id');
            fetch(`/get_employee_data/${employeeId}`)
                .then(response => response.json())
                .then(data => {
                    document.getElementById('name').value = data.name;
                    document.getElementById('surname').value = data.surname;
                    document.getElementById('role').value = data.role;
                    document.getElementById('group').value = data.group;
                    employeeIdInput.value = employeeId;
                    document.getElementById('modal-title').textContent = 'Uredi radnika';
                    submitButton.textContent = 'Spremi';
                    modal.classList.remove('hidden', 'opacity-0', 'pointer-events-none');
                });
        });
    });

    document.getElementById('employee-form').addEventListener('submit', function(event) {
        event.preventDefault();
        const url = this.action;
        const formData = new FormData(this);
        fetch(url, {
            method: 'POST',
            body: formData,
            headers: {
                'X-CSRFToken': getCookie('csrftoken')  // Ensure CSRF token is included
            },
        })
        .then(response => response.json())
        .then(data => {
            console.log('Success:', data);
            window.location.reload();  // Refresh the page to reflect the changes
        })
        .catch(error => console.error('Error:', error));
    });

    deleteButtons.forEach(button => {
        button.addEventListener('click', function() {
            const employeeId = this.getAttribute('data-id');
            if (confirm('Are you sure you want to delete this employee?')) {
                fetch(`/delete_employee/${employeeId}`, {
                    method: 'DELETE',
                    headers: {
                        'X-CSRFToken': getCookie('csrftoken'), // Get CSRF token from cookies
                        'Content-Type': 'application/json'
                    },
                }).then(response => {
                    if (response.ok) {
                        window.location.reload(); // Reload the page to reflect changes
                    } else {
                        console.error('Failed to delete:', response.status);
                    }
                }).catch(error => {
                    console.error('Error:', error);
                });
            }
        });
    });
    
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

    // Close modal interactions
    closeModalButtons.forEach(button => {
        button.addEventListener('click', () => {
            modal.classList.add('hidden', 'opacity-0', 'pointer-events-none');
        });
    });

    window.addEventListener('click', (event) => {
        if (event.target === modal) {
            modal.classList.add('hidden', 'opacity-0', 'pointer-events-none');
        }
    });

    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape') {
            modal.classList.add('hidden', 'opacity-0', 'pointer-events-none');
        }
    });

    form.addEventListener('submit', () => {
        modal.classList.add('hidden'); // Hide the modal after submitting
    });

    if (successMessage) {
        setTimeout(function() {
            successMessage.style.display = 'none';
        }, 2000);
    }
});
