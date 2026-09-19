document.addEventListener('DOMContentLoaded', () => {
    initFlashMessageDismissal();
    initTransactionFilters();
    initFileUploadPreview();
});

// Flash message auto-dismissal
function initFlashMessageDismissal() {
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(alert => {
        setTimeout(() => {
            alert.style.opacity = '0';
            setTimeout(() => alert.remove(), 500);
        }, 4000);
    });
}

// Client-side instant filtering for Transactions table
function initTransactionFilters() {
    const memberFilter = document.getElementById('filter-member');
    const accountFilter = document.getElementById('filter-account');
    const typeFilter = document.getElementById('filter-type');
    const tableRows = document.querySelectorAll('#transactions-table tbody tr');

    if (!memberFilter || !tableRows.length) return;

    function filterTable() {
        const selectedMember = memberFilter.value.toLowerCase();
        const selectedAccount = accountFilter.value.toLowerCase();
        const selectedType = typeFilter.value.toLowerCase();

        tableRows.forEach(row => {
            if (row.children.length === 1) return; // Skip "No records" row

            const memberText = row.children[1].textContent.toLowerCase();
            const accountText = row.children[2].textContent.toLowerCase();
            const typeText = row.children[4].textContent.toLowerCase();

            const matchMember = !selectedMember || memberText.includes(selectedMember);
            const matchAccount = !selectedAccount || accountText.includes(selectedAccount);
            const matchType = !selectedType || typeText.includes(selectedType);

            row.style.display = (matchMember && matchAccount && matchType) ? '' : 'none';
        });
    }

    memberFilter.addEventListener('change', filterTable);
    accountFilter.addEventListener('change', filterTable);
    typeFilter.addEventListener('change', filterTable);
}

// File Drag & Drop visual feedback
function initFileUploadPreview() {
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file');
    const fileLabel = document.getElementById('file-label');

    if (!dropZone || !fileInput) return;

    ['dragenter', 'dragover'].forEach(eventName => {
        dropZone.addEventListener(eventName, (e) => {
            e.preventDefault();
            dropZone.classList.add('highlight');
        }, false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, (e) => {
            e.preventDefault();
            dropZone.classList.remove('highlight');
        }, false);
    });

    dropZone.addEventListener('drop', (e) => {
        const dt = e.dataTransfer;
        const files = dt.files;
        fileInput.files = files;
        if (files.length > 0) {
            fileLabel.textContent = `Selected: ${files[0].name}`;
        }
    });

    fileInput.addEventListener('change', () => {
        if (fileInput.files.length > 0) {
            fileLabel.textContent = `Selected: ${fileInput.files[0].name}`;
        }
    });
}

// Generic API Delete helper
async function deleteEntity(endpoint, id, elementId) {
    if (!confirm('Are you sure you want to delete this item?')) return;

    try {
        const response = await fetch(`${endpoint}/${id}`, {
            method: 'DELETE',
            headers: { 'Content-Type': 'application/json' }
        });

        if (response.ok) {
            const el = document.getElementById(elementId);
            if (el) el.remove();
        } else {
            alert('Failed to delete item.');
        }
    } catch (err) {
        console.error('Error deleting entity:', err);
    }
}
