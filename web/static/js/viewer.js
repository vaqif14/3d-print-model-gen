import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { STLLoader } from 'three/addons/loaders/STLLoader.js';

export class CadViewer {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.scene = new THREE.Scene();
        this.scene.background = new THREE.Color(0x0a0a0f);

        this.camera = new THREE.PerspectiveCamera(45, this.container.clientWidth / this.container.clientHeight, 0.1, 1000);
        this.camera.position.set(50, 50, 100);

        this.renderer = new THREE.WebGLRenderer({ antialias: true });
        this.renderer.setSize(this.container.clientWidth, this.container.clientHeight);
        this.renderer.setPixelRatio(window.devicePixelRatio);
        this.renderer.shadowMap.enabled = true;
        this.container.appendChild(this.renderer.domElement);

        this.controls = new OrbitControls(this.camera, this.renderer.domElement);
        this.controls.enableDamping = true;
        this.controls.dampingFactor = 0.05;

        this.setupLights();
        this.setupGrid();

        this.mesh = null;
        this.animate();

        window.addEventListener('resize', () => this.onResize());
    }

    setupLights() {
        const ambient = new THREE.AmbientLight(0xffffff, 0.4);
        this.scene.add(ambient);

        const dir = new THREE.DirectionalLight(0xffffff, 0.8);
        dir.position.set(50, 100, 50);
        dir.castShadow = true;
        this.scene.add(dir);

        const fill = new THREE.DirectionalLight(0x58a6ff, 0.3);
        fill.position.set(-50, 20, -50);
        this.scene.add(fill);
    }

    setupGrid() {
        const grid = new THREE.GridHelper(200, 20, 0x30363d, 0x21262d);
        this.scene.add(grid);
    }

    loadSTL(url) {
        this.setStatus('loading', 'Loading mesh...');
        const loader = new STLLoader();
        loader.load(url, (geometry) => {
            if (this.mesh) {
                this.scene.remove(this.mesh);
                this.mesh.geometry.dispose();
                this.mesh.material.dispose();
            }

            geometry.computeVertexNormals();
            const material = new THREE.MeshStandardMaterial({
                color: 0x58a6ff,
                metalness: 0.1,
                roughness: 0.3,
                flatShading: false,
            });

            this.mesh = new THREE.Mesh(geometry, material);
            this.mesh.castShadow = true;
            this.mesh.receiveShadow = true;

            // Center and scale
            geometry.computeBoundingBox();
            const center = new THREE.Vector3();
            geometry.boundingBox.getCenter(center);
            this.mesh.position.sub(center);

            const size = new THREE.Vector3();
            geometry.boundingBox.getSize(size);
            const maxDim = Math.max(size.x, size.y, size.z);
            if (maxDim > 0) {
                const scale = 80 / maxDim;
                this.mesh.scale.setScalar(scale);
            }

            this.scene.add(this.mesh);
            this.setStatus('success', 'Mesh loaded');
        }, undefined, (err) => {
            console.error(err);
            this.setStatus('error', 'Failed to load mesh');
        });
    }

    clear() {
        if (this.mesh) {
            this.scene.remove(this.mesh);
            this.mesh.geometry.dispose();
            this.mesh.material.dispose();
            this.mesh = null;
        }
    }

    setStatus(type, text) {
        const el = document.getElementById('viewer-status');
        el.className = 'viewer-status ' + type;
        el.textContent = text;
    }

    onResize() {
        const w = this.container.clientWidth;
        const h = this.container.clientHeight;
        this.camera.aspect = w / h;
        this.camera.updateProjectionMatrix();
        this.renderer.setSize(w, h);
    }

    animate() {
        requestAnimationFrame(() => this.animate());
        this.controls.update();
        this.renderer.render(this.scene, this.camera);
    }
}
