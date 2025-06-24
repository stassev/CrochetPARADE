//Copyright (C) Svetlin Tassev

// This file is part of CrochetPARADE.

// CrochetPARADE is free software: you can redistribute it and/or modify it under 
// the terms of the GNU General Public License as published by the Free Software 
// Foundation, either version 3 of the License, or (at your option) any later version.

// CrochetPARADE is distributed in the hope that it will be useful, but WITHOUT 
// ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS 
// FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.

// You should have received a copy of the GNU General Public License along 
// with CrochetPARADE. If not, see <https://www.gnu.org/licenses/>.

// Global variables
let translateCanvas, rotateCanvas;
let currentTranslation = {
    x: 0,
    y: 0,
    z: 0
};
let currentRotation = {
    alpha: 0,
    beta: 0,
    gamma: 0
};
let translateMinMax = {
    x: 5,
    y: 5,
    z: 5
};
const rotateMinMax = {
    alpha: 180,
    beta: 180,
    gamma: 180
};
const pointR = 5;
const pointColor = '#ff0000';

export function returnRotational() {

    //console.log(`FINAL angles: alpha=${currentRotation.alpha.toFixed(3)}, beta=${currentRotation.beta.toFixed(3)}, gamma=${currentRotation.gamma.toFixed(3)}`);
    return [currentRotation.alpha, currentRotation.beta, currentRotation.gamma];
}

function dispatchMyCustomEvent(data) {
    const event = new CustomEvent('myCustomEvent', {
        detail: data // You can pass any data you want
    });
    document.dispatchEvent(event);
}

export function returnTranslation() {

    //console.log(`FINAL translations: x=${currentTranslation.x.toFixed(3)}, y=${currentTranslation.y.toFixed(3)}, z=${currentTranslation.z.toFixed(3)}`);
    return [currentTranslation.x, currentTranslation.y, currentTranslation.z];
}
// Initialize controls
export function initializeControls() {
    translateCanvas = setupCanvas('translateCanvas', handleTranslateInteraction);
    rotateCanvas = setupCanvas('rotateCanvas', handleRotateInteraction);

    setupInputs('translate', ['X', 'Y', 'Z'], setTranslation);
    setupInputs('rotate', ['Alpha', 'Beta', 'Gamma'], setRotation);

    setupSlider('translateZSlider', setTranslationZ);
    setupSlider('rotateGammaSlider', setRotationGamma);

    setupButton('resetTranslation', resetTranslation);
    setupButton('resetRotation', resetRotation);
    setupButton('resetTranslationMinMax', resetTranslationMinMax);

    //setupButton('3dbutton', resetTranslation);
    //setupButton('3dbutton', resetRotation);
    //setupButton('3dbutton', resetTranslationMinMax);
    drawTranslateCanvas();
    drawRotateCanvas();
    printValues('Translation', currentTranslation);
    printValues('Rotation', currentRotation);

    document.getElementById('transformButton').addEventListener('click', toggleControlPanel);
    document.getElementById('closeButton').addEventListener('click', hideControlPanel);

    // Initially hide the control panel
    //hideControlPanel();
}

// Setup functions
function setupCanvas(id, handler) {
    const canvas = document.getElementById(id);
    canvas.addEventListener('mousedown', handler);
    canvas.addEventListener('mousemove', handler);
    canvas.addEventListener('mouseup', handler);
    canvas.addEventListener('mouseleave', handler);
    return canvas;
}

function setupInputs(prefix, suffixes, setterFunction) {
    suffixes.forEach(suffix => {
        const input = document.getElementById(`${prefix}${suffix}Input`);
        input.addEventListener('change', () => {
            setterFunction(suffix.toLowerCase(), parseFloat(input.value));
            if (prefix === 'translate') {
                returnTranslation();
                dispatchMyCustomEvent();
            } else if (prefix === 'rotate') {
                returnRotational();
                dispatchMyCustomEvent();
            }
        });
    });
}


function setupSlider(id, setterFunction) {
    const slider = document.getElementById(id);
    slider.addEventListener('input', () => setterFunction(parseFloat(slider.value), false));
    slider.addEventListener('change', () => setterFunction(parseFloat(slider.value), true));
}

function setupButton(id, callback) {
    document.getElementById(id).addEventListener('click', callback);
}

// Drawing functions
function drawTranslateCanvas() {
    drawCanvas(translateCanvas, currentTranslation, translateMinMax, 'x', 'y');
}

function drawRotateCanvas() {
    drawCanvas(rotateCanvas, currentRotation, rotateMinMax, 'alpha', 'beta');
}

function drawCanvas(canvas, values, minMax, xKey, yKey) {
    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = '#e0e0e0';
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    // Draw axes
    ctx.strokeStyle = 'black';
    ctx.beginPath();
    ctx.moveTo(0, canvas.height / 2);
    ctx.lineTo(canvas.width, canvas.height / 2);
    ctx.moveTo(canvas.width / 2, 0);
    ctx.lineTo(canvas.width / 2, canvas.height);
    ctx.stroke();
    //const canvas = document.getElementById('rotateCanvas');
    //const ctx = canvas.getContext('2d');
    if (yKey === 'beta') {
        // Add labels to the axes
        ctx.font = '14px Arial';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';

        // Label for X-axis (green)
        ctx.fillStyle = 'green';
        ctx.fillText('Green', canvas.width - 23, canvas.height / 2 + 10);

        // Label for Y-axis (red)
        ctx.save();
        ctx.translate(canvas.width / 2, 20);
        ctx.rotate(-Math.PI / 2);
        ctx.fillStyle = 'red';
        ctx.fillText('Red', 0, -9);
        ctx.restore();
    }
    // Draw point
    const x = (values[xKey] + minMax[xKey]) / (2 * minMax[xKey]) * canvas.width;
    const y = canvas.height - (values[yKey] + minMax[yKey]) / (2 * minMax[yKey]) * canvas.height;
    if (yKey === 'beta')
        ctx.fillStyle = '#0075ff';
    else
        ctx.fillStyle = pointColor;
    ctx.beginPath();
    ctx.arc(x, y, pointR, 0, 2 * Math.PI);
    ctx.fill();
}

// Setter functions
function setTranslation(axis, value) {
    currentTranslation[axis] = value;
    updateMinMax('translate', currentTranslation, translateMinMax);
    updateInputsAndSlider('translate', currentTranslation);
    drawTranslateCanvas();
    printValues('Translation', currentTranslation);
}

function setTranslationZ(value, printFinal = false) {
    setTranslation('z', value);
    if (printFinal) {
        returnTranslation();

    }
    dispatchMyCustomEvent();
}


function setRotation(axis, value) {
    currentRotation[axis] = value;
    updateInputsAndSlider('rotate', currentRotation);
    drawRotateCanvas();
    printValues('Rotation', currentRotation);
}


function setRotationGamma(value, printFinal = false) {
    setRotation('gamma', value);
    if (printFinal) {
        returnRotational();

    }
    dispatchMyCustomEvent();
}

// Update functions
function updateMinMax(prefix, values, minMax) {
    Object.keys(values).forEach(key => {
        minMax[key] = Math.max(Math.ceil(Math.abs(values[key])), minMax[key]);
    });
    document.getElementById('translateZSlider').min = -minMax.z;
    document.getElementById('translateZSlider').max = minMax.z;
}

function updateInputsAndSlider(prefix, values) {
    Object.entries(values).forEach(([key, value]) => {
        document.getElementById(`${prefix}${key.charAt(0).toUpperCase() + key.slice(1)}Input`).value = value.toFixed(3);
    });
    if (prefix === 'translate') {
        document.getElementById('translateZSlider').value = values.z;
    } else {
        document.getElementById('rotateGammaSlider').value = values.gamma;
    }
}

// Helper functions
function printValues(label, values) {
    //console.log(`${label}: ${Object.entries(values).map(([k, v]) => `${k}: ${v.toFixed(3)}`).join(', ')}`);
}

export function resetTranslation() {
    setTranslation('x', 0);
    setTranslation('y', 0);
    setTranslation('z', 0);
    returnTranslation();
    dispatchMyCustomEvent();
}

export function resetRotation() {
    setRotation('alpha', 0);
    setRotation('beta', 0);
    setRotation('gamma', 0);
    returnRotational();
    dispatchMyCustomEvent();
}

export function resetTranslationMinMax() {
    translateMinMax = {
        x: 5,
        y: 5,
        z: 5
    };
    document.getElementById('translateZSlider').min = -translateMinMax.z;
    document.getElementById('translateZSlider').max = translateMinMax.z;
    drawTranslateCanvas();
    updateInputsAndSlider('translate', currentTranslation);
}

// Event handlers
function handleTranslateInteraction(e) {
    handleInteraction(e, translateCanvas, translateMinMax, setTranslation, 'x', 'y');
}

function handleRotateInteraction(e) {
    handleInteraction(e, rotateCanvas, rotateMinMax, setRotation, 'alpha', 'beta');
}

function handleInteraction(e, canvas, minMax, setterFunction, xKey, yKey) {
    const rect = canvas.getBoundingClientRect();
    const expansionFactor = 1.01; // 1% expansion

    let x = (e.clientX - rect.left) / canvas.width * (2 * minMax[xKey] * expansionFactor) - minMax[xKey] * expansionFactor;
    let y = minMax[yKey] * expansionFactor - (e.clientY - rect.top) / canvas.height * (2 * minMax[yKey] * expansionFactor);

    // Clamp values to the expanded range
    x = Math.max(-minMax[xKey], Math.min(minMax[xKey], x));
    y = Math.max(-minMax[yKey], Math.min(minMax[yKey], y));

    if (e.type === 'mousedown' || (e.type === 'mousemove' && e.buttons === 1)) {
        setterFunction(xKey, x);
        setterFunction(yKey, y);
        dispatchMyCustomEvent();
    } else if (e.type === 'mouseup') {
        if (canvas.id === 'translateCanvas') {
            returnTranslation();
            dispatchMyCustomEvent();
        } else if (canvas.id === 'rotateCanvas') {
            returnRotational();
            dispatchMyCustomEvent();
        }
    }
}



function showControlPanel() {
    document.getElementById('controlPanel').style.display = 'block';
}

function hideControlPanel() {
    document.getElementById('controlPanel').style.display = 'none';
}
var neverPressed = true;

function toggleControlPanel() {
    if (neverPressed) {
        initializeControls();
        neverPressed = false;
    }
    const controlPanel = document.getElementById('controlPanel');
    if (controlPanel.style.display === 'none' || controlPanel.style.display === '') {
        showControlPanel();
    } else {
        hideControlPanel();
    }
}

export function setTranslationValues(x, y, z) {
    setTranslation('x', x);
    setTranslation('y', y);
    setTranslation('z', z);
    returnTranslation();
}

export function setRotationAngles(alpha, beta, gamma) {
    setRotation('alpha', alpha);
    setRotation('beta', beta);
    setRotation('gamma', gamma);
    returnRotational();
}
// Initialize controls when the window loads
//window.addEventListener('load', initializeControls);
function checkForElement() {
    const element = document.getElementById('translateCanvas');
    if (element) {
        initializeControls();
        neverPressed = false;
        clearInterval(intervalId);
    }
}

const intervalId = setInterval(checkForElement, 100);