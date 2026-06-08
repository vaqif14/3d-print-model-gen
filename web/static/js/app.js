import { CadViewer } from './viewer.js';
import { ParamForm } from './params.js';
import { HistoryPanel } from './history.js';

const API_BASE = '';

class App {
    constructor() {
        this.viewer = new CadViewer('viewer');
        this.paramForm = new ParamForm('param-form', (key, val) => this.onParamChange(key, val));
        this.history = new HistoryPanel('history-tree');

        this.currentDesign = null;
        this.currentMeshId = null;
        this.designId = 'design-' + Math.random().toString(36).slice(2, 8);

        this.bindEvents();
    }

    bindEvents() {
        document.getElementById('btn-ai-generate').addEventListener('click', () => this.aiGenerate());
        document.getElementById('btn-regenerate').addEventListener('click', () => this.regenerate());
        document.getElementById('btn-export-stl').addEventListener('click', () => this.exportMesh('stl'));
        document.getElementById('btn-export-step').addEventListener('click', () => this.exportMesh('step'));
        document.getElementById('btn-branch').addEventListener('click', () => this.createBranch());
        document.getElementById('btn-new-branch').addEventListener('click', () => this.createBranch());

        // Image upload
        this.bindImageEvents();
    }

    bindImageEvents() {
        const dropzone = document.getElementById('image-dropzone');
        const input = document.getElementById('image-input');
        const preview = document.getElementById('image-preview');
        const controls = document.getElementById('image-controls');

        dropzone.addEventListener('click', () => input.click());

        dropzone.addEventListener('dragover', (e) => {
            e.preventDefault();
            dropzone.classList.add('dragover');
        });

        dropzone.addEventListener('dragleave', () => {
            dropzone.classList.remove('dragover');
        });

        dropzone.addEventListener('drop', (e) => {
            e.preventDefault();
            dropzone.classList.remove('dragover');
            if (e.dataTransfer.files.length) {
                this.handleImageFile(e.dataTransfer.files[0]);
            }
        });

        input.addEventListener('change', (e) => {
            if (e.target.files.length) {
                this.handleImageFile(e.target.files[0]);
            }
        });

        // Image sliders
        ['img-height', 'img-base', 'img-smooth'].forEach(id => {
            const slider = document.getElementById(id);
            const val = document.getElementById(id + '-val');
            slider.addEventListener('input', () => {
                val.textContent = slider.value;
            });
        });

        document.getElementById('btn-image-convert').addEventListener('click', () => this.convertImage());
    }

    async handleImageFile(file) {
        const preview = document.getElementById('image-preview');
        const controls = document.getElementById('image-controls');
        const dropzone = document.getElementById('image-dropzone');

        preview.src = URL.createObjectURL(file);
        preview.style.display = 'block';
        controls.style.display = 'block';
        dropzone.style.display = 'none';

        this.currentImageFile = file;
        this.setStatus('loading', 'Uploading image...');

        const form = new FormData();
        form.append('file', file);

        try {
            const res = await fetch(`${API_BASE}/api/image/upload`, {
                method: 'POST',
                body: form,
            });
            const data = await res.json();
            this.currentMeshId = data.image_id;
            this.viewer.loadSTL(data.stl_url);
            this.setStatus('success', 'Image uploaded');
            document.getElementById('btn-export-stl').disabled = false;
        } catch (err) {
            console.error(err);
            this.setStatus('error', 'Upload failed');
        }
    }

    async convertImage() {
        if (!this.currentMeshId) return;

        const body = {
            mesh_id: this.currentMeshId,
            max_height_mm: parseFloat(document.getElementById('img-height').value),
            base_thickness_mm: parseFloat(document.getElementById('img-base').value),
            smoothing: parseInt(document.getElementById('img-smooth').value),
            invert: document.getElementById('img-invert').checked,
        };

        this.setStatus('loading', 'Converting...');
        try {
            const res = await fetch(`${API_BASE}/api/image/convert`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body),
            });
            const data = await res.json();
            this.viewer.loadSTL(data.stl_url);
            this.setStatus('success', 'Converted: ' + data.volume_mm3 + ' mm³');
        } catch (err) {
            console.error(err);
            this.setStatus('error', 'Conversion failed');
        }
    }

    async aiGenerate() {
        const prompt = document.getElementById('ai-prompt').value.trim();
        if (!prompt) return;

        this.setStatus('loading', 'Parsing design intent...');
        try {
            const res = await fetch(`${API_BASE}/api/design/parse`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ prompt, printer: 'p2s' }),
            });
            this.currentDesign = await res.json();
            this.applyDesign(this.currentDesign);
        } catch (err) {
            console.error(err);
            this.setStatus('error', 'Failed to parse prompt');
        }
    }

    applyDesign(design) {
        // Show panels
        document.getElementById('params-section').style.display = 'block';
        document.getElementById('estimates-section').style.display = 'block';

        // Build param form
        this.paramForm.build(design.param_schema, design.params);

        // Update estimates
        document.getElementById('est-weight').textContent = design.estimates.weight_g + ' g';
        document.getElementById('est-cost').textContent = '$' + design.estimates.cost_usd;
        document.getElementById('est-time').textContent = design.estimates.time_hours + ' h';
        document.getElementById('est-volume').textContent = design.estimates.volume_mm3 + ' mm³';

        // Update material info
        const mat = design.material;
        document.querySelector('.material-name').textContent = mat;
        // Fetch material temps (hardcoded fallback)
        const temps = {
            'PLA': { nozzle: 210, bed: 60 },
            'PETG': { nozzle: 240, bed: 80 },
            'ABS': { nozzle: 240, bed: 105 },
            'ASA': { nozzle: 250, bed: 100 },
            'TPU': { nozzle: 220, bed: 50 },
            'Nylon': { nozzle: 260, bed: 90 },
            'PC': { nozzle: 280, bed: 110 },
        };
        const t = temps[mat] || temps['PETG'];
        document.getElementById('mat-nozzle').textContent = `Nozzle: ${t.nozzle}°C`;
        document.getElementById('mat-bed').textContent = `Bed: ${t.bed}°C`;

        // Enable buttons
        document.getElementById('btn-export-stl').disabled = false;
        document.getElementById('btn-export-step').disabled = false;
        document.getElementById('btn-branch').disabled = false;

        this.regenerate();
    }

    async regenerate() {
        if (!this.currentDesign) return;

        const params = this.paramForm.getValues();
        const body = {
            part_type: this.currentDesign.part_type,
            params: params,
            material: params.material || this.currentDesign.material,
            printer: params.printer || this.currentDesign.printer,
        };

        this.setStatus('loading', 'Generating geometry...');
        try {
            const res = await fetch(`${API_BASE}/api/geometry/generate`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body),
            });
            const data = await res.json();
            this.currentMeshId = data.mesh_id;

            // Load in viewer
            this.viewer.loadSTL(data.stl_url);

            // Validate
            this.validateMesh(data.mesh_id);

            // Save to history
            this.commitHistory(params, data);

        } catch (err) {
            console.error(err);
            this.setStatus('error', 'Generation failed');
        }
    }

    onParamChange(key, val) {
        // Debounce could be added here
        if (this.currentDesign) {
            this.currentDesign.params[key] = val;
        }
    }

    async validateMesh(meshId) {
        try {
            const res = await fetch(`${API_BASE}/api/mesh/validate/${meshId}`);
            const data = await res.json();
            this.renderValidation(data);
        } catch (err) {
            console.error(err);
        }
    }

    renderValidation(data) {
        const container = document.getElementById('validation-results');
        container.innerHTML = '';

        const items = [
            { label: 'Watertight', pass: data.watertight },
            { label: 'Faces', pass: true, value: data.face_count },
            { label: 'Volume', pass: data.volume_mm3 !== null, value: data.volume_mm3 ? data.volume_mm3 + ' mm³' : 'N/A' },
            { label: 'No Holes', pass: !data.has_holes },
        ];

        items.forEach(item => {
            const div = document.createElement('div');
            div.className = 'validation-item';

            const icon = document.createElement('span');
            icon.className = 'validation-icon ' + (item.pass ? 'pass' : 'fail');
            icon.textContent = item.pass ? '✓' : '✗';

            const text = document.createElement('span');
            text.textContent = item.label + (item.value !== undefined ? ': ' + item.value : '');

            div.appendChild(icon);
            div.appendChild(text);
            container.appendChild(div);
        });
    }

    async commitHistory(params, meshData) {
        const body = {
            design_id: this.designId,
            branch: 'main',
            message: `${this.currentDesign.part_type}: ${JSON.stringify(params)}`,
            params: params,
            estimates: {
                volume_mm3: meshData.volume_mm3,
                bounds_mm: meshData.bounds_mm,
            },
        };

        try {
            await fetch(`${API_BASE}/api/history/commit`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body),
            });
            this.refreshHistory();
        } catch (err) {
            console.error(err);
        }
    }

    async refreshHistory() {
        try {
            const res = await fetch(`${API_BASE}/api/history/tree/${this.designId}`);
            const tree = await res.json();
            this.history.render(tree);
        } catch (err) {
            console.error(err);
        }
    }

    async createBranch() {
        const name = prompt('Branch name:');
        if (!name) return;

        try {
            await fetch(`${API_BASE}/api/history/branch/${this.designId}?new_branch=${encodeURIComponent(name)}`, {
                method: 'POST',
            });
            this.refreshHistory();
        } catch (err) {
            console.error(err);
        }
    }

    exportMesh(format) {
        if (!this.currentMeshId) return;
        window.open(`${API_BASE}/api/mesh/download/${this.currentMeshId}/${format}`, '_blank');
    }

    setStatus(type, text) {
        this.viewer.setStatus(type, text);
    }
}

// Initialize
new App();
