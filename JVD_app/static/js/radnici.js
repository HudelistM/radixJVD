document.addEventListener('DOMContentLoaded', (event) => {
    const form = document.querySelector('.modal-content');
    const openModalButtons = document.querySelectorAll('.modal-open');
    const closeModalButtons = document.querySelectorAll('.modal-close');
    const overlay = document.querySelector('.modal-overlay');
    const modal = document.querySelector('.modal');
    const successMessage = document.getElementById('success-message');

    openModalButtons.forEach(button => {
        button.addEventListener('click', () => {
            modal.classList.remove('hidden');
            modal.classList.remove('opacity-0');
            modal.classList.remove('pointer-events-none');
        });
    });

    closeModalButtons.forEach(button => {
        button.addEventListener('click', () => {
            modal.classList.add('hidden');
            modal.classList.add('opacity-0');
            modal.classList.add('pointer-events-none');
        });
    });

    overlay.addEventListener('click', () => {
        modal.classList.add('hidden');
        modal.classList.add('opacity-0');
        modal.classList.add('pointer-events-none');
    });

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            modal.classList.add('hidden');
            modal.classList.add('opacity-0');
            modal.classList.add('pointer-events-none');
        }
    });
    form.addEventListener('submit', () => {
        modal.classList.add('hidden'); // Sakrij modalni prozor
    });
    
    if (successMessage) {
        setTimeout(function() {
            successMessage.style.display = 'none';
        }, 2000);
    }
});
