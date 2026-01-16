document.addEventListener('DOMContentLoaded', () => {
    const root = document.getElementById('file-structure');
    if (!root || !directoryStructure) return;

    // modal helper (Bootstrap 5)
    function openComplianceModal(dirName, pct) {
        const modalEl = document.getElementById('complianceModal');
        if (!modalEl) return;
        const dirEl = document.getElementById('modalDirName');
        if (dirEl) dirEl.textContent = dirName;

        const rateEl = document.getElementById('modalComplianceRate');
        if (rateEl) {
            rateEl.textContent = pct + '%';
            // reset any existing bg-* classes then add matching color
            rateEl.classList.remove('bg-success', 'bg-warning', 'bg-danger', 'bg-secondary');
            let badgeColor = 'bg-danger';
            if (pct > 70) {
                badgeColor = 'bg-success';
            } else if (pct > 40) {
                badgeColor = 'bg-warning';
            }
            rateEl.classList.add(badgeColor);
        }

        const list = document.getElementById('modalIssueList');
        if (list) {
            list.innerHTML = '';
            let pool = Array.isArray(window.guidelinesList) ? [...window.guidelinesList] : [];
            if (!pool.length) {
                pool = ['이미지 alt 속성 없음', '미니파이되지 않은 JS', '렌더링 차단 CSS'];
            }

            const sampleCount = Math.min(5, pool.length);
            for (let i = 0; i < sampleCount; i++) {
                const idx = Math.floor(Math.random() * pool.length);
                const entry = pool.splice(idx, 1)[0];
                let display;
                if (typeof entry === 'string') {
                    display = entry;
                } else if (entry && entry.guideline) {
                    display = `${entry.category}-${entry.id}. ${entry.guideline}`;
                } else {
                    display = JSON.stringify(entry);
                }
                const li = document.createElement('li');
                li.className = 'list-group-item py-2';
                li.textContent = display;
                list.appendChild(li);
            }
        }

        bootstrap.Modal.getOrCreateInstance(modalEl).show();
    }

    function createCaret(collapsed = true) {
        const caret = document.createElement('i');
        caret.className = collapsed ? 'fas fa-caret-right me-1' : 'fas fa-caret-down me-1';
        return caret;
    }

    function createFolderIcon(open = false) {
        const icon = document.createElement('i');
        icon.className = open ? 'fas fa-folder-open me-1 text-warning' : 'fas fa-folder me-1 text-warning';
        return icon;
    }

    function createFileIcon(filename) {
        const icon = document.createElement('i');
        const ext = filename.split('.').pop().toLowerCase();
        let cls = 'far fa-file-code me-1';
        if (['png', 'jpg', 'jpeg', 'svg', 'gif', 'webp'].includes(ext)) {
            cls = 'far fa-file-image me-1';
        } else if (['css'].includes(ext)) {
            cls = 'far fa-file-code me-1';
        } else if (['js', 'ts'].includes(ext)) {
            cls = 'far fa-file-code me-1';
        }
        icon.className = cls;
        return icon;
    }

    function render(parent, node, depth = 0) {
        for (const key in node) {
            if (key === '__files__') {
                node[key].forEach(file => {
                    const li = document.createElement('li');
                    li.className = 'file-item';
                    const span = document.createElement('span');
                    span.appendChild(createFileIcon(file));
                    span.appendChild(document.createTextNode(file));
                    li.appendChild(span);
                    parent.appendChild(li);
                });
            } else {
                const li = document.createElement('li');
                li.className = 'folder-item';

                // header row with flex to align name and bar horizontally
                const header = document.createElement('div');
                header.className = 'd-flex align-items-center w-100 gap-2';

                const span = document.createElement('span');
                span.className = 'folder-label d-inline-flex align-items-center';
                const caret = createCaret(true);
                const folderIcon = createFolderIcon(false);

                span.appendChild(caret);
                span.appendChild(folderIcon);
                span.appendChild(document.createTextNode(key));

                header.appendChild(span);

                const ul = document.createElement('ul');
                ul.classList.add('nested', 'hidden');

                // Top-level directory: add mock progress bar
                if (depth === 0) {
                    const progressWrapper = document.createElement('div');
                    progressWrapper.className = 'progress flex-grow-1 ms-2';
                    progressWrapper.style.height = '10px';

                    // mock percentage between 30-90
                    const pct = Math.floor(Math.random() * 60) + 30;

                    // pick color based on percentage
                    let barColorClass = 'bg-danger';
                    if (pct > 70) {
                        barColorClass = 'bg-success';
                    } else if (pct > 40) {
                        barColorClass = 'bg-warning';
                    }

                    const progressBar = document.createElement('div');
                    progressBar.className = `progress-bar ${barColorClass}`;
                    progressBar.style.width = `${pct}%`;
                    progressWrapper.title = `가이드라인 준수율: ${pct}%`;
                    progressWrapper.style.cursor = 'pointer';
                    progressWrapper.addEventListener('click', (ev) => {
                        ev.stopPropagation();
                        openComplianceModal(key, pct);
                    });
                    progressWrapper.appendChild(progressBar);
                    header.appendChild(progressWrapper);
                }

                // append header then nested UL
                li.appendChild(header);
                li.appendChild(ul);
                parent.appendChild(li);

                // toggle when clicking anywhere on the header (caret/folder/title)
                header.addEventListener('click', () => {
                    ul.classList.toggle('hidden');
                    const collapsed = ul.classList.contains('hidden');
                    caret.className = collapsed ? 'fas fa-caret-right me-1' : 'fas fa-caret-down me-1';
                    folderIcon.className = collapsed ? 'fas fa-folder me-1 text-warning' : 'fas fa-folder-open me-1 text-warning';
                });

                render(ul, node[key], depth + 1);
            }
        }
    }

    render(root, directoryStructure);
});