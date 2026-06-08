export class HistoryPanel {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.commits = [];
        this.currentCommitId = null;
    }

    render(treeData) {
        this.commits = treeData.commits || [];
        this.container.innerHTML = '';

        const branches = {};
        this.commits.forEach(c => {
            const b = c.branch || 'main';
            if (!branches[b]) branches[b] = [];
            branches[b].push(c);
        });

        Object.entries(branches).forEach(([branchName, commits]) => {
            const branchDiv = document.createElement('div');
            branchDiv.className = 'history-branch';

            const nameEl = document.createElement('div');
            nameEl.className = 'history-branch-name';
            nameEl.textContent = branchName;
            branchDiv.appendChild(nameEl);

            commits.forEach(c => {
                const commitDiv = document.createElement('div');
                commitDiv.className = 'history-commit';
                if (c.commit_id === this.currentCommitId) {
                    commitDiv.classList.add('active');
                }

                const idEl = document.createElement('div');
                idEl.className = 'history-commit-id';
                idEl.textContent = c.commit_id;

                const msgEl = document.createElement('div');
                msgEl.className = 'history-commit-msg';
                msgEl.textContent = c.message;

                commitDiv.appendChild(idEl);
                commitDiv.appendChild(msgEl);

                commitDiv.addEventListener('click', () => {
                    this.currentCommitId = c.commit_id;
                    this.render(treeData);
                    if (this.onCheckout) this.onCheckout(c);
                });

                branchDiv.appendChild(commitDiv);
            });

            this.container.appendChild(branchDiv);
        });
    }

    addCommit(commit) {
        this.commits.push(commit);
        this.currentCommitId = commit.commit_id;
    }

    setOnCheckout(handler) {
        this.onCheckout = handler;
    }
}
