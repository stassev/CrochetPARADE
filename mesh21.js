///
///

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
///
import * as THREE from 'three';
import {
    OrbitControls
} from './OrbitControls.js';
import {
    GLTFExporter
} from './GLTFExporter.js';
import {
    resetTranslation,
    resetRotation,
    resetTranslationMinMax,
    setTranslationValues,
    returnRotational,
    returnTranslation,
    setRotationAngles
} from './transform_controls.js';

//import {
//    SVGRenderer
//} from 'three/addons/renderers/SVGRenderer.js'
export default function Generate3DModel(json0, renderer, scene, scene1, backgroundColor, c_was_pressed, factor_radius, requestedInfo) {



    resetTranslation();
    resetRotation();
    resetTranslationMinMax();
    const arrowLength = 1.3; // Length of the arrows
    const arrowColors = {
        x: 0xc80000, // Red for X-axis
        y: 0x00c800, // Green for Y-axis
        z: 0x0000c8 // Blue for Z-axis
    };

    const arrowX = new THREE.ArrowHelper(new THREE.Vector3(1, 0, 0), new THREE.Vector3(0, 0, 0), arrowLength, arrowColors.x);
    const arrowY = new THREE.ArrowHelper(new THREE.Vector3(0, 1, 0), new THREE.Vector3(0, 0, 0), arrowLength, arrowColors.y);
    const arrowZ = new THREE.ArrowHelper(new THREE.Vector3(0, 0, 1), new THREE.Vector3(0, 0, 0), arrowLength, arrowColors.z);
    const axesGroup = new THREE.Group();
    console.log(arrowX);
    const radius = 0.01; // Adjust this value to change the thickness of the arrow shaft
    const cylinderGeometry = new THREE.CylinderGeometry(radius, radius, 0.8 * arrowLength, 32);
    const cylinderMaterial = new THREE.MeshBasicMaterial({
        color: arrowColors.x
    });
    const cylinderMaterialY = new THREE.MeshBasicMaterial({
        color: arrowColors.y
    });
    const cylinderMaterialZ = new THREE.MeshBasicMaterial({
        color: arrowColors.z
    });
    const cylinder = new THREE.Mesh(cylinderGeometry, cylinderMaterial);
    cylinder.position.set(0, 0.4 * arrowLength, 0);

    const cylinderY = new THREE.Mesh(cylinderGeometry, cylinderMaterialY);
    cylinderY.position.set(0, 0.4 * arrowLength, 0);

    const cylinderZ = new THREE.Mesh(cylinderGeometry, cylinderMaterialZ);
    cylinderZ.position.set(0, 0.4 * arrowLength, 0);
    arrowX.add(cylinder);
    arrowY.add(cylinderY);
    arrowZ.add(cylinderZ);
    axesGroup.add(arrowX, arrowY, arrowZ);

    var planeMesh, gridHelper;
    const planeSize = 10; // Adjust size as needed
    const planeGeometry = new THREE.PlaneGeometry(planeSize, planeSize);
    const planeMaterial = new THREE.MeshBasicMaterial({
        color: 0xfce1f9, // Gray color
        opacity: 0.7,
        side: THREE.DoubleSide,
        transparent: true
    });

    // Add event listener to your button

    planeMesh = new THREE.Mesh(planeGeometry, planeMaterial);

    // Position the plane at the center of mass (COM)
    planeMesh.position.set(0, 0, 0);

    // Rotate the plane to be parallel to the x-y plane
    planeMesh.rotation.z = -Math.PI / 2;

    // Add grid lines
    gridHelper = new THREE.GridHelper(planeSize, 10, 0x000000, 0x000000);
    gridHelper.position.set(0, 0, 0.001);
    gridHelper.rotation.x = Math.PI / 2;


    // Create a guiding cylinder
    const cylinderLength = 10; // Length of the cylinder
    const cylinderRadius = 0.01; // Radius of the cylinder
    const GcylinderGeometry = new THREE.CylinderGeometry(cylinderRadius, cylinderRadius, cylinderLength, 32);
    const GcylinderMaterial = new THREE.MeshBasicMaterial({
        color: 0x0f90b7, // Gray color
        //opacity: 0.9,
        //side: THREE.DoubleSide,
        //transparent: true
    });

    // Create the cylinder mesh
    const guidingCylinder = new THREE.Mesh(GcylinderGeometry, GcylinderMaterial);

    // Initially position the cylinder at (0, 0, 0)
    guidingCylinder.position.set(0, 0, 0);


    // Add event listener to your checkbox
    const checkbox = document.getElementById('toggleGuidesCheckbox');
    checkbox.addEventListener('change', function() {
        let guidesVisible = this.checked;
        planeMesh.visible = guidesVisible;
        gridHelper.visible = guidesVisible;
        guidingCylinder.visible = guidesVisible;
        //arrowX.visible = guidesVisible;
        //arrowY.visible = guidesVisible;
        //arrowZ.visible = guidesVisible; 
        //axesGroup.visible = guidesVisible;

    });
    const checkboxAxes = document.getElementById('toggleGuideAxesCheckbox');
    checkboxAxes.addEventListener('change', function() {
        let guidesVisible = this.checked;
        //planeMesh.visible = guidesVisible;
        //gridHelper.visible = guidesVisible;
        //arrowX.visible = guidesVisible;
        //arrowY.visible = guidesVisible;
        //arrowZ.visible = guidesVisible; 
        axesGroup.visible = guidesVisible;
    });

    // Initialize visibility based on checkbox state
    planeMesh.visible = checkbox.checked;
    gridHelper.visible = checkbox.checked;
    guidingCylinder.visible = checkbox.checked;
    //arrowX.visible = checkbox.checked;
    //arrowY.visible = checkbox.checked;
    //arrowZ.visible = checkbox.checked;
    axesGroup.visible = checkboxAxes.checked;

    if (renderer != null)
        renderer.dispose();

    if (scene1 != null) {
        while (scene1.children.length > 0) {
            scene1.remove(scene1.children[0]);
        }
    }
    if (scene != null) {
        while (scene.children.length > 0) {
            scene.remove(scene.children[0]);
        }
    }
    if (renderer != null)
        renderer.dispose();


    //    const rendererSVG = new SVGRenderer();
    //    rendererSVG.setSize(window.innerWidth, window.innerHeight);
    //    rendererSVG.setClearColor(0xffffff);
    //    document.body.appendChild(rendererSVG.domElement);
    //    rendererSVG.domElement.setAttribute('xmlns', 'http://www.w3.org/2000/svg');


    var str = JSON.parse(JSON.stringify(json0)); //JSON.parse12.json0);
    //console.log(str)
    // Create a scene
    scene = new THREE.Scene();
    scene.add(axesGroup);
    scene.add(planeMesh);
    scene.add(gridHelper);
    scene.add(guidingCylinder);

    scene1 = new THREE.Scene();
    //scene.add(arrowX);
    //scene.add(arrowY);
    //scene.add(arrowZ);

    function updateAxesVisualization(data) {

        // Update guidingCylinder position
        guidingCylinder.position.set(
            data.tx + data.com.x,
            data.ty + data.com.y,
            data.tz + data.com.z
        );
        const position = new THREE.Vector3(
            data.tx + data.com.x,
            data.ty + data.com.y,
            data.tz + data.com.z
        );
        axesGroup.position.copy(position);
        //axesGroup.setRotationFromQuaternion(new THREE.Quaternion(
        //    data.quaternion.x,
        //    data.quaternion.y,
        //    data.quaternion.z,
        //    data.quaternion.w
        //));
        // Convert quaternion to Euler angles (assuming ZYX order)
        const euler = new THREE.Euler().setFromQuaternion(
            new THREE.Quaternion(
                data.quaternion.x,
                data.quaternion.y,
                data.quaternion.z,
                data.quaternion.w
            ),
            'XYZ'
        );

        // Calculate rotation axes
        //const zAxis = new THREE.Vector3(0, 0, 1); // Z-axis is always global Z for first rotation

        // Y-axis is rotated around Z
        //const yAxis = new THREE.Vector3(0, 1, 0)
        //    .applyAxisAngle(new THREE.Vector3(0, 0, 1), euler.z);

        // X-axis is rotated around Z, then around rotated Y
        //const xAxis = new THREE.Vector3(1, 0, 0)
        //    .applyAxisAngle(new THREE.Vector3(0, 0, 1), euler.z)
        //    .applyAxisAngle(yAxis, euler.y);
        const zAxis = new THREE.Vector3(0, 0, 1)
            .applyAxisAngle(new THREE.Vector3(0, 1, 0), euler.y)
            .applyAxisAngle(new THREE.Vector3(1, 0, 0), euler.x);

        // Get the current direction of arrowY (yAxis0)
        //const yAxis0tmp = arrowY.line.geometry.attributes.position.array.slice(3, 6);
        //const yAxis0 = new THREE.Vector3().fromArray(yAxis0tmp).normalize();


        // Y-axis: rotated by first angle (alpha)
        const yAxis = new THREE.Vector3(0, 1, 0)
            .applyAxisAngle(new THREE.Vector3(1, 0, 0), euler.x);
        //if (yAxis0.dot(yAxis)) {
        if (Math.abs(data.ry) > Math.PI / 2.0) {
            yAxis.x = -yAxis.x;
            yAxis.y = -yAxis.y;
            yAxis.z = -yAxis.z;
        }

        // X-axis: global X (last rotation axis)
        const xAxis = new THREE.Vector3(1, 0, 0);
        // Update the arrows
        //.position.copy(position);
        arrowX.setDirection(xAxis);

        //arrowY.position.copy(position);
        arrowY.setDirection(yAxis);

        //arrowZ.position.copy(position);
        arrowZ.setDirection(zAxis);
        //arrowX.position.copy(position);
        //arrowY.position.copy(position);
        //arrowZ.position.copy(position);
        //arrowX.setRotationFromQuaternion(new THREE.Quaternion(
        //    data.quaternion.x,
        //    data.quaternion.y,
        //    data.quaternion.z,
        //    data.quaternion.w
        //));
        //arrowY.setRotationFromQuaternion(new THREE.Quaternion(
        //    data.quaternion.x,
        //    data.quaternion.y,
        //    data.quaternion.z,
        //    data.quaternion.w
        //));
        //arrowZ.setRotationFromQuaternion(new THREE.Quaternion(
        //    data.quaternion.x,
        //    data.quaternion.y,
        //    data.quaternion.z,
        //    data.quaternion.w
        //));
    }

    //set background color
    if (backgroundColor === '')
        scene.background = new THREE.Color("rgb(210, 210, 210)");
    else
        scene.background = new THREE.Color(backgroundColor);


    // Create a camera




    // Create a renderer

    const domElement = document.getElementById('view3d').querySelector('canvas');
    if (domElement)
        domElement.parentNode.removeChild(domElement);

    var Dimen = 3;

    const container = document.getElementById('view3d'); // Replace 'yourContainerId' with the actual ID of your predefined HTML element


    renderer = new THREE.WebGLRenderer();

    renderer.setPixelRatio(window.devicePixelRatio);
    // renderer.setSize(window.innerWidth, window.innerHeight);


    // Set the size of the renderer
    var width = container.clientWidth; // Use the client width of the container
    var height = container.clientHeight; // Use the client height of the container

    if (width < 50)
        width = window.innerWidth;
    if (height < 50)
        height = window.innerHeight;

    renderer.setSize(width, height);

    const camera = new THREE.PerspectiveCamera(75, width / height, 0.1, 100);


    renderer.domElement.setAttribute("id", "3DRender");
    //document.body.appendChild(renderer.domElement);
    container.appendChild(renderer.domElement);

    function on3dViewResize() {
        var width = container.clientWidth;
        var height = container.clientHeight;
        if (width < 50) width = window.innerWidth;
        if (height < 50) height = window.innerHeight;

        renderer.setSize(width, height);
        // Adjust pixel ratio
        //   var pixelRatio = window.devicePixelRatio;
        //var newPixelRatio = pixelRatio * width / height;
        //renderer.setPixelRatio(newPixelRatio);
        // Update the camera aspect ratio
        camera.aspect = width / height;
        camera.updateProjectionMatrix();
    }

    // Event listener for the class change in '3dview'
    var view = document.getElementById('view3d');
    var observer = new MutationObserver(function(mutations) {
        mutations.forEach(function(mutation) {
            if (mutation.attributeName === "class") {
                on3dViewResize();
            }
        });
    });

    const controlsContainer = document.getElementById('controlPanel');

    // Add event listener for the object input



    //function updateScene(objectValue) {
    //   // Your code to update the scene based on the object value
    //   console.log('Object:', objectValue);
    //   // Add your logic here
    //}
    const view3dElement = document.getElementById('view3d');
    //view3dElement.appendChild(controlsContainer);

    observer.observe(view, {
        attributes: true
    });

    //normalize node positions
    var xm = 0.0,
        ym = 0.0,
        zm = 0.0,
        r2 = 0.0,
        tot = 0.0;
    for (var o of str.objects) {
        //console.log(o.pos)
        var pos = o.pos.split('|')[0].split(',').map(Number);
        if (pos.length == 2)
            pos[2] = 0;
        xm += pos[0];
        ym += pos[1];
        zm += pos[2];
        tot += 1.0;
    }
    //var std = Math.sqrt((xm2 - xm * xm / tot + ym2 - ym * ym / tot + zm2 - zm * zm / tot) / (tot))
    xm = xm / tot;
    ym = ym / tot;
    zm = zm / tot;
    for (let o of str.objects) {
        let pos = o.pos.split('|')[0].split(',').map(Number);
        if (pos.length == 2)
            pos[2] = 0;
        r2 = Math.max(r2, (pos[0] - xm) ** 2 + (pos[1] - ym) ** 2 + (pos[2] - zm) ** 2);
    }
    r2 = Math.sqrt(r2);
    for (let o of str.objects) {
        let pos = o.pos.split('|')[0].split(',').map(Number);
        if (pos.length == 2) {
            pos[2] = 0;
            Dimen = 2;
        }
        o['pos'] = [(pos[0] - xm) / r2, (pos[1] - ym) / r2, (pos[2] - zm) / r2];
    }
    var maxObjects;

    // Create a geometry for the nodes
    const nodeGeometry = new THREE.SphereGeometry(0.006, 8, 4);

    // Create a material for the nodes
    const nodeMaterial = new THREE.MeshLambertMaterial({
        color: new THREE.Color(0.9, 0, 0.9)
    });

    const selectedNodeMaterial = new THREE.MeshBasicMaterial({
        color: new THREE.Color(0, 0.8, 0)
    });

    const selectedObjectMaterial = new THREE.MeshBasicMaterial({
        color: new THREE.Color(0.0, 0.0, 0.3)
    });

    var NODES = [];
    var NODEShidden = [];
    var NODES1 = [];
    // Create the nodes
    let objectValue = -1;
    //console.log(str);
    str.objects.forEach((obj) => {
        if (str.edges.find((edge) => obj._gvid === edge.head) === undefined) {
            // Do things if no match is found (i.e., if it's undefined)
            objectValue++;
        }
        obj['objectValue'] = objectValue;
        if (obj.label.split('|')[0] !== "hidden") {
            const pos = obj.pos; //.split(',').map(Number);
            const node = new THREE.Mesh(nodeGeometry, nodeMaterial);
            node.position.set(pos[0], pos[1], pos[2]);
            node['name_long'] = "<span style='font-size: 16px; font-weight: bold;'>(" + obj.name + ") [" + obj.label.split('|')[0] + "]</span><br><b>C1:</b> &hellip;" + obj.label.split('|')[1] + "&hellip;";
            node['name'] = "<span style='font-size: 16px; font-weight: bold;'>(" + obj.name + ") [" + obj.label.split('|')[0] + "]</span>";
            node['type'] = 0;
            node['id0'] = obj.name.split('|')[0];
            node['row'] = [parseInt(obj.name.split('|')[0].split(',')[0]), parseInt(obj.name.split('|')[0].split(',')[1])];
            node['Color'] = obj.label.split('|')[2];
            node['objectValue'] = objectValue;

            scene.add(node);
            NODES.push(node);
            //console.log(obj);
        }
    });
    maxObjects = objectValue;



    //Find average edge scaling factor
    var lenF = 0.0,
        totLen = 0.0;
    for (let edge of str.edges) {
        edge['Color'] = edge.label;

        const tail = str.objects.find((obj) => obj._gvid === edge.tail);
        const head = str.objects.find((obj) => obj._gvid === edge.head);
        edge['objectValue'] = tail['objectValue'];

        edge['length'] = Math.sqrt((tail.pos[0] - head.pos[0]) ** 2 + (tail.pos[1] - head.pos[1]) ** 2 + (tail.pos[2] - head.pos[2]) ** 2);
        if (['red', 'blue'].includes(edge.color)) {
            lenF += edge.length;
            totLen += parseFloat(edge.len);
        }
    }
    lenF = (lenF / totLen);
    var STATS = '';
    STATS += '\n';
    STATS += ("Radius of the sphere bounding the project is " + String(Math.round(10 / lenF) / 10) + " chain stitches.\nThe sphere is centered at center of the 3D view,\ncoinciding with the center of mass of the stitches.\n");
    //console.log(lenF)
    for (let edge of str.edges) {
        edge['stretch'] = (edge.length / lenF) / parseFloat(edge.len);
        //console.log(edge.stretch)
    }



    // 1. Add a directional light
    const directionalLight = new THREE.DirectionalLight(0xffffff, 3);
    directionalLight.position.set(0, 0, 3);
    scene.add(directionalLight);

    const directionalLight1 = new THREE.DirectionalLight(0xffffff, 3);
    directionalLight1.position.set(0, 0, -3);
    scene.add(directionalLight1);

    // 2. Add an ambient light
    const ambientLight = new THREE.AmbientLight(0x404040, 3);
    scene.add(ambientLight);

    // Create a material for the edges
    const edgeMaterialBlue = new THREE.MeshLambertMaterial({
        color: new THREE.Color(0, 0, 0.9)
    });

    const edgeMaterialRed = new THREE.MeshLambertMaterial({
        color: new THREE.Color(0.9, 0, 0)
    });

    const edgeMaterialGray = new THREE.MeshLambertMaterial({
        color: new THREE.Color(0.7, 0.7, 0.7)
    });

    const selectedEdgeMaterial = new THREE.LineBasicMaterial({
        color: new THREE.Color(0., 0.8, 0),
        linewidth: 2
    });

    const selectedRowMaterial = new THREE.MeshBasicMaterial({
        color: 0xffff65
    });

    var stLen = {};
    var stTot = {};



    /////////////////////

    //var colorscale = {
    //    0: [165, 0, 38],
    //    1: [215, 48, 39],
    //    2: [244, 109, 67],
    //    3: [253, 174, 97],
    //    4: [254, 224, 144],
    //    5: [224, 243, 248],
    //    6: [171, 217, 233],
    //    7: [116, 173, 209],
    //    8: [69, 117, 180],
    //    9: [49, 54, 149]
    //}

    var colorscale = {
        0: [0., 0, 0.9],
        1: [0., 0, 0.9],
        2: [0.6, 0.6, 0.6],
        3: [0.6, 0.6, 0.6],
        4: [0.6, 0.6, 0.6],
        5: [0.9, 0, 0],
        6: [0.9, 0, 0]
    };

    function color(key) {
        if (key >= 6)
            return colorscale[6].map(function(channel) {
                return channel;
            });
        else if (key <= 0)
            return colorscale[0].map(function(channel) {
                return channel;
            });
        var keys = Object.keys(colorscale).map(Number);
        var lowerKey = Math.max.apply(null, keys.filter(function(k) {
            return k <= key;
        }));
        var upperKey = Math.min.apply(null, keys.filter(function(k) {
            return k > key;
        }));
        var lowerColor = colorscale[lowerKey];
        var upperColor = colorscale[upperKey];
        var t = (key - lowerKey) / (upperKey - lowerKey);
        var interpolatedColor = lowerColor.map(function(channel, i) {
            return channel + t * (upperColor[i] - channel);
        });
        return interpolatedColor.map(function(channel) {
            return channel;
        });
    }


    /////////////////////

    //// Create the edges
    str.edges.forEach((edge) => {

        const tail = str.objects.find((obj) => obj._gvid === edge.tail);
        const head = str.objects.find((obj) => obj._gvid === edge.head);
        let objectValue = tail.objectValue;
        if (!objectValue)
            objectValue = head.objectValue;
        //console.log('ok', objectValue, tail, head);
        edge['start'] = [tail.pos[0], tail.pos[1], tail.pos[2]];
        edge['end'] = [head.pos[0], head.pos[1], head.pos[2]];

        const A = (new THREE.Vector3(tail.pos[0], tail.pos[1], tail.pos[2]));
        const B = (new THREE.Vector3(head.pos[0], head.pos[1], head.pos[2]));

        var row = [parseInt(head.name.split('|')[0].split(',')[0]), parseInt(head.name.split('|')[0].split(',')[1])];
        if ((head.label.split('|')[0] == 'ch')) {
            if (!('ch' in stLen)) {
                stLen['ch'] = 0;
                stTot['ch'] = 0;
            }
            stLen['ch'] += edge.stretch;
            stTot['ch']++;
        } else if ((edge.color == "red")) {
            if (!(head.label.split('|')[0] in stLen)) {
                stLen[head.label.split('|')[0]] = 0;
                stTot[head.label.split('|')[0]] = 0;
            }
            stLen[head.label.split('|')[0]] += edge.stretch;
            stTot[head.label.split('|')[0]]++;
        }


        // const geometry = new THREE.BufferGeometry().setFromPoints(points);
        var material;
        if (edge.color === "red")
            material = edgeMaterialRed;
        else
            material = edgeMaterialBlue;
        //var rgbArray = edge.rgb
        //const color = new THREE.Color(rgbArray[0], rgbArray[1], rgbArray[2]);
        //const material = new THREE.LineBasicMaterial({
        //    color: color,
        //    linewidth: 2
        //});
        //const line = new THREE.Line(geometry, material);



        ///
        const distance = A.distanceTo(B);
        var radius = 0.003;
        var non = false;
        edge['gray'] = 0;
        if (edge.color === 'gray') {
            edge['gray'] = 1;
            radius /= 5.0;
            material = edgeMaterialGray;
            non = true;
        }
        // 2. Create a THREE.CylinderGeometry object
        const geometry = new THREE.CylinderGeometry(radius, radius, distance, 5);

        // 3. Position the cylinder between the two points
        const midpoint = new THREE.Vector3().addVectors(A, B).divideScalar(2);
        const line = new THREE.Mesh(geometry, material);
        line.position.copy(midpoint);

        // 4. Orient the cylinder along the vector formed by the two points
        const direction = new THREE.Vector3().subVectors(B, A).normalize();
        const quaternion = new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 1, 0), direction);
        line.quaternion.copy(quaternion);

        ///

        line['Color'] = edge.Color;
        line['color'] = edge.color;
        line['type'] = 1;
        //"(" + obj.name + ") [" + obj.label.split('|')[0] + "]<br>" + obj.label.split('|')[1]
        line['name_long'] = "<span style='font-size: 16px; font-weight: bold;'>(" + head.name + ") [" + head.label.split('|')[0] + "]</span><br><b>C1:</b> &hellip;" + head.label.split('|')[1] + "&hellip;<br>" + 'stretched by ' + Math.round(100 * (edge['stretch'] - 1)) + '%';
        line['name'] = "<span style='font-size: 16px; font-weight: bold;'>(" + head.name + ") [" + head.label.split('|')[0] + '] stretched by ' + Math.round(100 * (edge['stretch'] - 1)) + '%</span>';
        line['id0'] = (edge.head).toString() + "-" + (edge.tail).toString();
        line['row'] = row;
        line['stretch'] = edge.stretch;
        scene.add(line);



        var arrowhead;

        // Create a cylinder for the arrowhead; create scene1 objects
        if (!non) {
            const arrowheadGeometry = new THREE.CylinderGeometry(radius, radius * 1.7, distance * 0.2, 10);
            const arrowheadMaterial = new THREE.MeshBasicMaterial({
                color: material.color,
                transparent: true,
                opacity: 0.8
            });
            arrowhead = new THREE.Mesh(arrowheadGeometry, arrowheadMaterial);

            // Position the arrowhead at the midpoint between points A and B
            const arrowheadMidpoint = new THREE.Vector3().addVectors(A, B).divideScalar(2);
            arrowhead.position.copy(arrowheadMidpoint);

            // Orient the arrowhead along the vector formed by the two points
            const arrowheadDirection = new THREE.Vector3().subVectors(B, A).normalize();
            const arrowheadQuaternion = new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 1, 0), arrowheadDirection);
            arrowhead.setRotationFromQuaternion(arrowheadQuaternion);
            arrowhead['row'] = row;
            arrowhead['stretch'] = edge.stretch;
            arrowhead['is_arrow'] = true;
            arrowhead['Color'] = edge.Color;
            arrowhead['type'] = 2;
            // Add the arrowhead to the scene
            scene.add(arrowhead);



            // Create a buffer geometry



            // 3. Position the cylinder between the two points

            const line1 = new THREE.Mesh(geometry, new THREE.MeshBasicMaterial({
                color: edge.Color
            }));

            line1.position.copy(midpoint);

            // 4. Orient the cylinder along the vector formed by the two points
            line1.quaternion.copy(quaternion);
            line1['objectValue'] = objectValue;
            // Add the line to the scene
            scene1.add(line1);
            NODES1.push(line1);
        }
        ///



        if (!(non)) {
            line['objectValue'] = objectValue;
            NODES.push(line);
            arrowhead['objectValue'] = objectValue;
            NODES.push(arrowhead);
        } else {
            line['objectValue'] = objectValue;
            NODEShidden.push(line);
        }
    });
    //console.log(NODES)

    STATS += '\n';
    STATS += 'Average vertical (horizontal for chains) stretching of stitches:\n';
    //console.log(stLen)
    for (let g of Object.keys(stLen))
        if (g !== 'hidden')
            STATS += g + '=' + String(Math.round((stLen[g] / stTot[g] - 1) * 100)) + '%\n';

    STATS += '\n';
    var originalMaterials = [];
    for (var i = 0; i < NODES.length; i++)
        originalMaterials.push(NODES[i].material);

    //scene.fog = new THREE.Fog(0xcccccc, 0.1, 10);
    //scene.fog1 = new THREE.FogExp2(0xcccccc, 0.1);

    //controls
    const controls = new OrbitControls(camera, renderer.domElement);

    controls.enableZoom = true; // Enable zooming
    controls.enablePan = true; // Enable panning
    controls.enableRotate = true; // Enable rotation
    controls.minDistance = 0.01; // Minimum zoom distance
    controls.maxDistance = 20; // Maximum zoom distance
    controls.enableDamping = false; // Enable smooth camera movements

    //controls.update() must be called after any manual changes to the camera's transform
    camera.position.set(0, 0, 2);
    controls.update();

    camera.lookAt(0, 0, 0);
    var wasMouseDown = true;
    var rotateAndSave = false;
    var rotateAndSaveSizeSet = -1;
    var canvasClicked = false;
    var timeoutQ = true;
    var timeoutID = null;

    function onMouseDown(event) {
        if (event.shiftKey && event.button === 0 && event.target === renderer.domElement)
            timeoutQ = !timeoutQ;
        if (!timeoutQ) {
            if (timeoutID != null)
                clearTimeout(timeoutID);
        } else {
            var myLabel = document.getElementById('myLabel');
            try {
                document.body.removeChild(myLabel);
            } catch (error) {}
        }
        if ((event.button === 0) && (canvasClicked)) { // Left mouse button
            wasMouseDown = true;
            rotateAndSave = false;
        }

    }
    document.addEventListener('mousedown', onMouseDown);

    ///Display name of node:


    // Set up the raycaster and mouse position
    var raycaster = new THREE.Raycaster();
    //raycaster.params.Precision = 0.00001;


    var mouse = new THREE.Vector2();

    var I = null;
    var Iold = null;

    // Handle the click event
    var oldmaterial = null;

    function createLabel() {
        var label = document.createElement('div');
        label.setAttribute('id', 'myLabel');
        label.style.position = 'absolute';
        label.style.textAlign = 'center';
        //const rect = renderer.domElement.offsetLeft();
        label.style.top = renderer.domElement.offsetTop + 'px';
        label.style.left = (renderer.domElement.offsetLeft + renderer.domElement.offsetWidth / 2) + 'px';

        label.style.transform = 'translate(-50%, 0)';
        label.style.backgroundColor = 'white';
        label.style.padding = '5px';
        label.style.fontSize = '14pt';
        label.style.width = renderer.domElement.offsetWidth * 0.9 + 'px';
        label.style.zIndex = '1000';
        return label;
    }


    function onMove(event) {

        if (requestedInfo && timeoutQ) {
            // Calculate the mouse position
            //mouse.x = ((event.clientX) / window.innerWidth) * 2 - 1;
            //mouse.y = -((event.clientY) / window.innerHeight) * 2 + 1;
            const rect = renderer.domElement.getBoundingClientRect();
            mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
            mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
            //console.log(event.clientX, event.clientY)
            // Set the raycaster position
            raycaster.setFromCamera(mouse, camera);

            // Get the intersected objects
            var intersects = raycaster.intersectObjects(NODES, false);
            intersects = intersects.filter((element) => (element.object.visible === true) && (!('is_arrow' in element.object)));


            // If there is an intersected object, display its name
            //console.log(intersects[0])
            //if (intersects.length > 0) {
            var label = false;
            if (intersects.length != 0) {
                label = createLabel();
            }
            if (intersects.length == 0) {
                I = null;
            } else if (intersects.length == 1) {
                I = intersects[0];
                label.innerHTML = "<span style='overflow-wrap: break-word; word-wrap: break-word;'>" + I.object.name_long + "</span>";
            } else {
                I = null;
                for (var i of intersects) {
                    if (i.object.type == 0) {
                        //console.log(i)
                        I = i;
                        break;
                    }
                }
                if (I == null)
                    I = intersects[0];

                label.innerHTML = "<span style='overflow-wrap: break-word; word-wrap: break-word;'>" + I.object.name_long + "</span>";
            }

            if ((Iold != null) && ((I == null) || (Iold.object.id0 != I.object.id0)))
                Iold.object.material = oldmaterial;
            //change colors of selected
            if ((I != null) && (Iold == null || (Iold.object.id0 != I.object.id0))) {
                oldmaterial = I.object.material;
                if (I.object.type == 0)
                    I.object.material = selectedNodeMaterial;
                else
                    I.object.material = selectedEdgeMaterial;
            }


            Iold = I;
            //



            var labelOld = document.getElementById('myLabel');
            try {
                if ((I == null) && (labelOld))
                    document.body.removeChild(labelOld);
                if ((!(labelOld)) && (label))
                    document.body.appendChild(label);
                if ((I != null) && (labelOld)) {
                    document.body.removeChild(labelOld);
                    document.body.appendChild(label);
                    //document.body.replaceChild(label, labelOld);
                }
            } catch (error) {}
        }
    }

    //}
    //if ('mousemove' in getEventListeners(document))
    //    for (var a of getEventListeners(document).mousemove)
    //        document.removeEventListener(a.type, a.listener)
    document.addEventListener('mousemove', onMove);
    // Add the click event listener

    function onWindowResize() {

        //camera.aspect = window.innerWidth / window.innerHeight;
        //camera.updateProjectionMatrix();

        //renderer.setSize(window.innerWidth, window.innerHeight);

        on3dViewResize();

    }


    window.addEventListener('resize', onWindowResize);
    var showArrows = true;

    var rowNumber = -1000;
    document.addEventListener('keydown', handleKeyDown);
    document.addEventListener('keyup', handleKeyUp);

    document.addEventListener('click', function(event) {
        if (event.target !== renderer.domElement) {
            canvasClicked = false;
        } else
            canvasClicked = true;
    });

    function ScaleRadii(f) {
        for (let i of NODES) {
            if (i.type == 1 || i.type == 2) {
                let h = i.geometry.parameters.height;
                let rt = i.geometry.parameters.radiusTop * f;
                let rb = i.geometry.parameters.radiusBottom * f;
                let n = i.geometry.parameters.radialSegments;
                i.geometry.dispose();
                i.geometry = new THREE.CylinderGeometry(rt, rb, h, n);
            } else if (i.type == 0) {
                let r = i.geometry.parameters.radius * f;
                i.geometry.dispose();
                i.geometry = new THREE.SphereGeometry(r, 8, 4);
            }
        }
        for (let i of NODEShidden)
            if (i.type == 1 || i.type == 2) {
                let h = i.geometry.parameters.height;
                let rt = i.geometry.parameters.radiusTop * f;
                let rb = i.geometry.parameters.radiusBottom * f;
                let n = i.geometry.parameters.radialSegments;
                i.geometry.dispose();
                i.geometry = new THREE.CylinderGeometry(rt, rb, h, n);
            }
        for (let i of NODES1) {
            let h = i.geometry.parameters.height;
            let rt = i.geometry.parameters.radiusTop * f;
            let rb = i.geometry.parameters.radiusBottom * f;
            let n = i.geometry.parameters.radialSegments;
            i.geometry.dispose();
            i.geometry = new THREE.CylinderGeometry(rt, rb, h, n);
        }
    }


    var RESETCOLORS = true;
    var HIDE = str.objects.length - 1;

    function dispatchMyEvent(data) {
        const event = new CustomEvent('myEvent', {
            detail: data // You can pass any data you want
        });
        document.dispatchEvent(event);
    }
    //Search and highlight
    function handleKeyDown(event) {
        if (canvasClicked && (event.key === 'i')) {
            requestedInfo = !requestedInfo;
            dispatchMyEvent([c_was_pressed, factor_radius, requestedInfo]);
            if (timeoutID != null)
                clearTimeout(timeoutID);
            let myLabel = document.getElementById('myLabel');
            //myLabel.style.display = 'none';
            try {
                document.body.removeChild(myLabel);
            } catch (error) {}
        }
        if (canvasClicked && (event.key === 'c')) {
            setTimeout(function() {
                c_was_pressed = true;

                showArrows = false;
                for (let i of NODES) {
                    i.material = new THREE.MeshLambertMaterial({
                        color: new THREE.Color(i.Color)
                    });
                    if (('is_arrow' in i) || i.type == 0)
                        i.visible = false;
                }
                for (let i of NODEShidden)
                    i.visible = false;
                ScaleRadii(4 / factor_radius); // show all radii as twice the default;
                factor_radius = 4;
                dispatchMyEvent([c_was_pressed, factor_radius, requestedInfo]);
            }, 200);
        }
        if (canvasClicked && ((event.key === '+') || (event.key === '=') || (event.key === '-')) && (event.ctrlKey || event.metaKey)) {
            //console.log(NODES)
            event.preventDefault();
            setTimeout(function() {

                let f = 1.259921;
                if (event.key === '-')
                    f = 1.0 / f;
                factor_radius *= f;
                ScaleRadii(f);
                dispatchMyEvent([c_was_pressed, factor_radius, requestedInfo]);
            }, 300);
        }
        if (canvasClicked && (event.key === 'v')) {
            setTimeout(function() {
                event.preventDefault();
                showArrows = !showArrows;
                if (showArrows) {
                    var [x, y] = str.objects[HIDE].name.split('|')[0].split(',');

                    for (var i = 0; i < NODES.length; i++) {
                        if (((NODES[i].row[0] == parseInt(x)) && (NODES[i].row[1] <= parseInt(y))) ||
                            ((NODES[i].row[0] < parseInt(x)))) {
                            if ('is_arrow' in NODES[i])
                                NODES[i].visible = true;
                        }
                    }

                } else {
                    for (let i of NODES)
                        if ('is_arrow' in i)
                            i.visible = false;
                }
            }, 300);
        }
        if (canvasClicked && (event.key === 's')) {
            event.preventDefault();
            setTimeout(function() {

                for (var i = 0; i < NODES.length; i++) {
                    if ('stretch' in NODES[i])
                        NODES[i].material = new THREE.MeshLambertMaterial({
                            color: new THREE.Color(...color(7 * (NODES[i].stretch - 1.0) + 3))
                        });
                    else
                        NODES[i].material = edgeMaterialGray;
                }
            }, 200);
        }
        if (canvasClicked && (event.key === 'f' && (event.ctrlKey || event.metaKey))) {
            event.preventDefault();
            setTimeout(function() {

                if (rowNumber != -1000) {
                    for (let i = 0; i < NODES.length; i++) {
                        NODES[i].material = originalMaterials[i];
                    }
                }
                var rn = null;
                rn = (prompt('Enter a row number or stitch coordinate (row,stitch number; e.g. 2,4) to be highlighted'));
                var rr = [];
                if (rn) {
                    for (var r of rn.split(new RegExp('[^0-9]+')))
                        if (r !== '')
                            rr.push(parseInt(r));
                    if (rr.length == 1) {
                        rowNumber = rr[0];
                        //console.log(NODES)
                        for (let i = 0; i < NODES.length; i++) {
                            if (NODES[i].row[0] == rowNumber) {
                                NODES[i].material = selectedRowMaterial;
                            }
                        }
                    } else if (rr.length == 2) {
                        //console.log(NODES)
                        rowNumber = rr[0];
                        for (let i = 0; i < NODES.length; i++) {
                            if ((NODES[i].row[0] == rowNumber) && (NODES[i].row[1] == rr[1])) {
                                NODES[i].material = selectedRowMaterial;
                            }
                        }
                    }
                }
            }, 300);
        }
    }


    function handleKeyUp(event) {
        if (canvasClicked && event.key === 'Escape') {
            event.preventDefault();
            if (!(event.ctrlKey || event.metaKey)) {
                c_was_pressed = false;
                for (let i = 0; i < NODES.length; i++) {
                    NODES[i].material = originalMaterials[i];
                    NODES[i].visible = true;
                }
                for (let i = 0; i < NODEShidden.length; i++) {
                    NODEShidden[i].visible = true;
                }
                RESETCOLORS = true;
                HIDE = str.objects.length - 1;

                ScaleRadii(1 / factor_radius); // show all radii as normal;
                factor_radius = 1;
                dispatchMyEvent([c_was_pressed, factor_radius, requestedInfo]);
            } else {
                HIDE = 0;
                RESETCOLORS = false;
                NODES[0].visible = true;
                NODES[0].material = originalMaterials[0];
                for (let i = 1; i < NODES.length; i++) {
                    NODES[i].material = originalMaterials[i];
                    NODES[i].visible = false;
                }
                for (let i = 0; i < NODEShidden.length; i++) {
                    //NODEShidden[i].material = originalMaterials[i];
                    NODEShidden[i].visible = false;
                }
            }
        }
    }
    //Search and hide.

    document.addEventListener('keydown', handleKeyDownHide, true);

    function handleKeyDownHide(event) {
        if ((canvasClicked) && (event.key === 'r')) {
            wasMouseDown = false;
        }
        if ((canvasClicked) && (event.key === 'o')) {
            rotateAndSave = true;
            wasMouseDown = false;
        }

        if (canvasClicked && (event.key === 'p')) {
            setTimeout(function() {
                saveSvg(rotateAndSave);
            }, 300);
        }
        if (canvasClicked && (event.key === 'h' && (event.ctrlKey || event.metaKey))) {


            event.preventDefault();
            setTimeout(function() {
                if (rowNumber != -1000) {
                    for (let i = 0; i < NODES.length; i++) {
                        NODES[i].material = originalMaterials[i];
                        NODES[i].visible = true;
                    }
                }
                //var rn = null
                //rn = (prompt('Enter a row number or stitch coordinate (row,stitch number; e.g. 2,4). All stitches after that will be hidden'));

                var rn = null;
                rn = (prompt('Enter a row number or stitch coordinate (row,stitch number; e.g. 2,4). All stitches after that will be hidden'));
                var rr = [];
                if (rn) {
                    for (let r of rn.split(new RegExp('[^0-9]+')))
                        if (r !== '')
                            rr.push(parseInt(r));
                    if (rr.length == 1) {
                        rowNumber = rr[0];
                        //console.log(NODES)
                        for (let i = 0; i < NODES.length; i++) {
                            if (NODES[i].row[0] > rowNumber) {
                                NODES[i].visible = false;
                            }
                        }
                        for (let i = 0; i < NODEShidden.length; i++) {
                            if (NODEShidden[i].row[0] > rowNumber) {
                                NODEShidden[i].visible = false;
                            }
                        }

                        RESETCOLORS = false;

                        HIDE = str.objects.findIndex((obj) => obj.name.split('|')[0] === String(rr[0] + 1) + ',' + String(0));
                        HIDE--;
                        if (HIDE == -2) { //searching for last element
                            HIDE = str.objects.length - 1;
                            //while ((str.objects[HIDE].label.split('|')[0] === "hidden") && HIDE >= 0)
                            //    HIDE--
                        }

                        if (HIDE == -1)
                            HIDE = 0;
                    } else if (rr.length == 2) {
                        //console.log(NODES)
                        rowNumber = rr[0];
                        for (var i = 0; i < NODES.length; i++) {
                            if (((NODES[i].row[0] == rowNumber) && (NODES[i].row[1] > rr[1])) || (NODES[i].row[0] > rowNumber)) {
                                NODES[i].visible = false;
                            }
                        }

                        for (let i = 0; i < NODEShidden.length; i++) {
                            if (((NODEShidden[i].row[0] == rowNumber) && (NODEShidden[i].row[1] > rr[1])) || (NODEShidden[i].row[0] > rowNumber)) {
                                NODEShidden[i].visible = false;
                            }
                        }

                        RESETCOLORS = false;

                        HIDE = str.objects.findIndex((obj) => obj.name.split('|')[0] === String(rr[0]) + ',' + String(rr[1]));
                        if (HIDE == -1)
                            HIDE = 0;

                    } {
                        let myLabel = document.getElementById('myLabel');
                        //myLabel.style.display = 'none';
                        try {
                            document.body.removeChild(myLabel);
                        } catch (error) {}
                    }
                    if (requestedInfo) {
                        let label = createLabel();
                        //console.log(str.objects[HIDE].name)
                        label.innerHTML = "<span style='font-size: 16px; font-weight: bold;'>" + str.objects[HIDE].name + '</span>';
                        document.body.appendChild(label);
                        if (timeoutID != null)
                            clearTimeout(timeoutID);
                        if (timeoutQ)
                            timeoutID = setTimeout(() => {
                                var myLabel = document.getElementById('myLabel');
                                //myLabel.style.display = 'none';
                                try {
                                    document.body.removeChild(myLabel);
                                } catch (error) {}
                            }, 10000);
                    }
                }
            }, 300);

        }
    }

    //Search and hide.

    document.addEventListener('keydown', handleKeyDownHideAnim);


    function handleKeyDownHideAnim(event) {

        if (canvasClicked && (event.key === 'a')) {
            event.preventDefault();
            if ((event.ctrlKey || event.metaKey)) {
                if (RESETCOLORS) {
                    RESETCOLORS = false;
                    HIDE = str.objects.length - 1;
                }
                if (HIDE > str.objects.length)
                    HIDE = str.objects.length - 1;
                HIDE--;
                while ((HIDE >= 0) && (str.objects[HIDE].label.split('|')[0] === "hidden"))
                    HIDE--;

                if (HIDE < 0)
                    HIDE = 0;
                let [x, y] = str.objects[HIDE].name.split('|')[0].split(',');

                for (let i = 0; i < NODES.length; i++) {
                    if (((NODES[i].row[0] >= parseInt(x)) && (NODES[i].row[1] > parseInt(y))) ||
                        ((NODES[i].row[0] > parseInt(x)))) {
                        NODES[i].visible = false;
                    }
                }

                for (let i = 0; i < NODEShidden.length; i++) {
                    if (((NODEShidden[i].row[0] >= parseInt(x)) && (NODEShidden[i].row[1] > parseInt(y))) ||
                        ((NODEShidden[i].row[0] > parseInt(x)))) {
                        NODEShidden[i].visible = false;
                    }
                }

            } else {
                HIDE++;
                if (HIDE > str.objects.length - 1)
                    HIDE = str.objects.length - 1;
                //while ((str.objects[HIDE].label.split('|')[0] === "hidden") && HIDE >= 0)
                //    HIDE--

                while ((HIDE < str.objects.length) && (str.objects[HIDE].label.split('|')[0] === "hidden"))
                    HIDE++;


                if (HIDE >= str.objects.length)
                    HIDE = str.objects.length - 1;
                if (HIDE == str.objects.length - 1 && str.objects[HIDE].label.split('|')[0] === "hidden")
                    while ((HIDE >= 0) && (str.objects[HIDE].label.split('|')[0] === "hidden"))
                        HIDE--;
                if ((HIDE < str.objects.length)) {
                    if (str.objects[HIDE].label.split('|')[0] !== "hidden") {
                        let [x, y] = str.objects[HIDE].name.split('|')[0].split(',');

                        for (let i = 0; i < NODES.length; i++) {
                            if ((NODES[i].row[0] <= parseInt(x)) && (NODES[i].row[1] <= parseInt(y))) {
                                if (!((!showArrows) && ('is_arrow' in NODES[i])))
                                    NODES[i].visible = true;
                            }
                        }

                        for (let i = 0; i < NODEShidden.length; i++) {
                            if ((NODEShidden[i].row[0] <= parseInt(x)) && (NODEShidden[i].row[1] <= parseInt(y))) {
                                NODEShidden[i].visible = true;
                            }
                        }
                    }
                }
            }

            if (requestedInfo) {
                {
                    let myLabel = document.getElementById('myLabel');
                    //myLabel.style.display = 'none';
                    try {
                        document.body.removeChild(myLabel);
                    } catch (error) {}
                }
                let label = createLabel();

                //label.innerHTML = "<span style='font-size: 16px; font-weight: bold;'>" + str.objects[HIDE].name + '</span>'
                label.innerHTML = "<span style='overflow-wrap: break-word; word-wrap: break-word;'><span style='font-size: 16px; font-weight: bold;'>(" + str.objects[HIDE].name + ") [" + str.objects[HIDE].label.split('|')[0] + "]</span><br><b>C1:</b> &hellip;" + str.objects[HIDE].label.split('|')[1] + "&hellip;</span>";
                document.body.appendChild(label);
                if (timeoutID != null)
                    clearTimeout(timeoutID);
                if (timeoutQ)
                    timeoutID = setTimeout(() => {
                        var myLabel = document.getElementById('myLabel');
                        try {
                            document.body.removeChild(myLabel);
                        } catch (error) {}
                    }, 10000);
            }

            if (c_was_pressed) {
                for (let i of NODES) {
                    if (('is_arrow' in i) || i.type == 0)
                        i.visible = false;
                }
                for (let i of NODEShidden)
                    i.visible = false;
            }

        }
    }
    const symbolMap = {
        'ch': 'M-5,0 A5,5 0 1,1 5,0 A5,5 0 1,1 -5,0',
        'ss': 'M-5,0 A5,10 0 1,1 5,0 A5,10 0 1,1 -5,0 Z',
        'sc': 'M171.94102,111.30121 H179.71246 M175.82674,117.09468 V105.50773',
        'hdc': 'M186.2474,99.048099 V80.157868',
        'dc': 'M172.89806,96.912628 V73.520279 M170.84091,82.837921 L174.95521,85.213321',
        'tr': 'M102.7556,85.196435 L106.8699,87.571832 M104.81275,102.98371 V70.587124 M102.7556,82.021436 L106.8699,84.396833',
        'dtr': 'M124.91581,102.3795 V61.773159 M122.85866,75.853306 L126.97296,78.228703 M122.85866,78.499138 L126.97296,80.874535 M122.85866,81.14497 L126.97296,83.520367',
        'trtr': 'M143.53007,101.48366 V53.386772 M141.47292,70.641918 L145.58722,73.017315 M141.47292,73.28775 L145.58722,75.663147 M141.47292,75.933582 L145.58722,78.308979 M141.47292,78.579417 L145.58722,80.954814',
        'rsc': 'M131.74584,151.77464 H139.51728 M135.63156,157.56811 V145.98116 M132.48897,145.41015 C133.19121,144.42701 133.70618,144.28657 134.40842,144.28657 C135.11065,144.28657 136.09379,145.45696 136.93648,145.45696 C137.77917,145.45696 138.57503,144.38019 138.57503,144.38019',
        'scbl': 'M131.74584,151.77464 H139.51728 M135.63156,157.56811 V145.98116 M132.05252,161.34418 A3.5790462,2.8758667 0 0 1 135.63156,158.46831 A3.5790462,2.8758667 0 0 1 139.21061,161.34418',
        'scfl': 'M131.74584,151.77464 H139.51728 M135.63156,157.56811 V145.98116 M132.05252,158.33667 A3.5790462,2.8758667 0 0 0 135.63156,161.21254 A3.5790462,2.8758667 0 0 0 139.21061,158.33667',
        'hdcfl': 'M64.900616,100.54621 V81.655976 M61.321573,100.71371 A3.5790462,2.8758667 0 0 0 64.90062,103.58957 A3.5790462,2.8758667 0 0 0 68.479666,100.71371',
        'dcfl': 'M81.887972,99.159791 V75.767442 M79.830822,85.085084 L83.945122,87.460484 M78.308924,99.327293 A3.5790462,2.8758667 0 0 0 81.88797,102.20316 A3.5790462,2.8758667 0 0 0 85.46701,99.327293',
        'trfl': 'M104.81275,102.98371 V70.587124 M102.7556,82.021436 L106.8699,84.396833 M102.7556,85.196435 L106.8699,87.571832 M101.23371,103.15121 A3.5790462,2.8758667 0 0 0 104.81275,106.02707 A3.5790462,2.8758667 0 0 0 108.39179,103.15121',
        'dtrfl': 'M124.91581,102.3795 V61.773159 M122.85866,75.853306 L126.97296,78.228703 M122.85866,78.499138 L126.97296,80.874535 M122.85866,81.14497 L126.97296,83.520367 M121.33676,102.547 A3.5790462,2.8758667 0 0 0 124.91581,105.42286 A3.5790462,2.8758667 0 0 0 128.49486,102.547',
        'trtrfl': 'M143.53007,101.48366 V53.386772 M141.47292,70.641918 L145.58722,73.017315 M141.47292,73.28775 L145.58722,75.663147 M141.47292,75.933582 L145.58722,78.308979 M141.47292,78.579417 L145.58722,80.954814 M139.95103,101.65115 A3.5790462,2.8758667 0 0 0 143.53008,104.52702 A3.5790462,2.8758667 0 0 0 147.10912,101.65115',
        'hdcbl': 'M64.900616,100.54621 V81.655976 M61.321573,104.16475 A3.5790462,2.8758667 0 0 1 64.90062,101.28889 A3.5790462,2.8758667 0 0 1 68.479666,104.16475',
        'dcbl': 'M81.887972,99.159791 V75.767442 M79.830822,85.085084 L83.945122,87.460484 M78.308924,102.77833 A3.5790462,2.8758667 0 0 1 81.88797,99.90247 A3.5790462,2.8758667 0 0 1 85.46701,102.77833',
        'trbl': 'M104.81275,102.98371 V70.587124 M102.7556,82.021436 L106.8699,84.396833 M102.7556,85.196435 L106.8699,87.571832 M101.23371,106.60225 A3.5790462,2.8758667 0 0 1 104.81275,103.72639 A3.5790462,2.8758667 0 0 1 108.39179,106.60225',
        'dtrbl': 'M124.91581,102.3795 V61.773159 M122.85866,75.853306 L126.97296,78.228703 M122.85866,78.499138 L126.97296,80.874535 M122.85866,81.14497 L126.97296,83.520367 M121.33676,105.99804 A3.5790462,2.8758667 0 0 1 124.91581,103.12218 A3.5790462,2.8758667 0 0 1 128.49486,105.99804',
        'trtrbl': 'M143.53007,101.48366 V53.386772 M141.47292,70.641918 L145.58722,73.017315 M141.47292,73.28775 L145.58722,75.663147 M141.47292,75.933582 L145.58722,78.308979 M141.47292,78.579417 L145.58722,80.954814 M139.95103,105.10219 A3.5790462,2.8758667 0 0 1 143.53008,102.22633 A3.5790462,2.8758667 0 0 1 147.10912,105.10219',
        'rscfl': 'M131.74584,151.77464 H139.51728 M135.63156,157.56811 V145.98116 M132.58916,145.41015 C133.2914,144.42701 133.80637,144.28657 134.50861,144.28657 C135.21084,144.28657 136.19398,145.45696 137.03667,145.45696 C137.87936,145.45696 138.67522,144.38019 138.67522,144.38019 M132.05252,158.33667 A3.5790462,2.8758667 0 0 0 135.63156,161.21254 A3.5790462,2.8758667 0 0 0 139.21061,158.33667',
        'rscbl': 'M131.74584,151.77464 H139.51728 M135.63156,157.56811 V145.98116 M132.58916,145.41015 C133.2914,144.42701 133.80637,144.28657 134.50861,144.28657 C135.21084,144.28657 136.19398,145.45696 137.03667,145.45696 C137.87936,145.45696 138.67522,144.38019 138.67522,144.38019 M132.05252,161.34418 A3.5790462,2.8758667 0 0 1 135.63156,158.46831 A3.5790462,2.8758667 0 0 1 139.21061,161.34418',
        'fphdc': 'M37.880373,159.91315 V141.02292 M37.880363,159.78142 A4.7955728,4.7955728 0 0 1 42.310895,162.74181 A4.7955728,4.7955728 0 0 1 41.271345,167.96798 A4.7955728,4.7955728 0 0 1 36.045177,169.00753 A4.7955728,4.7955728 0 0 1 33.084791,164.577',
        'fpdc': 'M66.781348,166.26735 V142.875 M64.724198,152.19264 L68.838498,154.56804 M66.781342,166.13465 A4.7955728,4.7955728 0 0 1 71.211873,169.09499 A4.7955728,4.7955728 0 0 1 70.172323,174.32116 A4.7955728,4.7955728 0 0 1 64.946155,175.36071 A4.7955728,4.7955728 0 0 1 61.985769,170.93022',
        'fptr': 'M88.787161,166.55591 V134.15932 M86.730011,145.59363 L90.844311,147.96903 M86.730011,148.76863 L90.844311,151.14403 M88.787148,166.42292 A4.7955728,4.7955728 0 0 1 93.217679,169.38330 A4.7955728,4.7955728 0 0 1 92.178129,174.60947 A4.7955728,4.7955728 0 0 1 86.951961,175.64902 A4.7955728,4.7955728 0 0 1 83.991575,171.21849',
        'bphdc': 'M37.880373,159.91315 V141.02292 M37.880383,159.78142 A4.7955728,4.7955728 0 0 0 33.449851,162.74181 A4.7955728,4.7955728 0 0 0 34.489401,167.96798 A4.7955728,4.7955728 0 0 0 39.715569,169.00753 A4.7955728,4.7955728 0 0 0 42.675955,164.577',
        'bpdc': 'M66.781348,166.26735 V142.875 M64.724198,152.19264 L68.838498,154.56804 M66.781364,166.13465 A4.7955728,4.7955728 0 0 0 62.350833,169.09504 A4.7955728,4.7955728 0 0 0 63.390383,174.32120 A4.7955728,4.7955728 0 0 0 68.616551,175.36075 A4.7955728,4.7955728 0 0 0 71.576937,170.93022',
        'bptr': 'M88.787161,166.55591 V134.15932 M86.730011,145.59363 L90.844311,147.96903 M86.730011,148.76863 L90.844311,151.14403 M88.78717,166.42292 A4.7955728,4.7955728 0 0 0 84.356639,169.38330 A4.7955728,4.7955728 0 0 0 85.396189,174.60947 A4.7955728,4.7955728 0 0 0 90.622357,175.64902 A4.7955728,4.7955728 0 0 0 93.582743,171.21849',
        'bpsc': 'M29.10417,197.88098 H36.87561 M32.98989,203.67445 V192.0875 M32.989899,203.54151 A4.7955728,4.7955728 0 0 0 28.559367,206.50190 A4.7955728,4.7955728 0 0 0 29.598917,211.72806 A4.7955728,4.7955728 0 0 0 34.825085,212.76761 A4.7955728,4.7955728 0 0 0 37.785471,208.33708',
        'fpsc': 'M29.10417,197.88098 H36.87561 M32.98989,203.67445 V192.0875 M32.98988,203.54151 A4.7955728,4.7955728 0 0 1 37.420411,206.50190 A4.7955728,4.7955728 0 0 1 36.380862,211.72806 A4.7955728,4.7955728 0 0 1 31.154693,212.76761 A4.7955728,4.7955728 0 0 1 28.194307,208.33708',
        'line': 'M0,-5 L0,5',
        'longsc': 'M-10,33 H10 M0,43.051791 V21.459442 M0,42.746442 A13.596,25.696 0 0 1 13.595998,68.442442 A13.596,25.696 0 0 1 0,94.138442 M-13.595998,30',
        'longdc': 'M-3.389164,26.333015 L12.162136,35.308015 M0,0 C2.475,10.605 7.475,39.235 7.065,60.815 C6.66,82.355 3.53,103.595 0.36,158.375 M-12.162136,20',
        'longtr': 'M-3.389164,26.333015 L12.162136,35.308015 M-3.389164,36.899015 L12.162136,45.874015 M0,0 C2.475,10.605 7.475,54.095 7.065,75.675 C6.66,97.215 3.53,122.455 0.36,177.235 M-12.162136,20',
        'hdc3puff': 'M57.120701,31.14763 C55.060803,33.956587 53.492106,36.543907 53.492106,40.042647 C53.492106,43.599357 54.964508,46.479837 57.024409,48.11287 M57.262236,31.14763 C59.322134,33.956587 60.796733,36.543907 60.796733,40.042647 C60.796733,43.600657 59.322033,46.45643 57.262032,48.98448 M57.196217,31.257148 L57.196217,48.836517',
        'hdc4puff': 'M39.205329,30.997373 C37.972062,33.811537 36.976602,36.403667 37.033097,39.908907 C37.090527,43.472217 37.972061,46.358037 39.205330,48.890787 M39.059053,30.997373 C40.292320,33.811537 41.287780,36.403667 41.231284,39.908907 C41.173854,43.472217 40.290321,46.358037 39.056821,48.890787 M39.11983,31.117972 C36.421815,32.153600 33.285264,36.292047 33.370944,39.955787 C33.454124,43.512507 36.429274,47.570997 39.076499,48.775107 M39.123628,31.117972 C41.821644,32.153600 44.958194,36.292047 44.872514,39.955787 C44.789334,43.512507 41.814184,47.570997 39.167074,48.775107',
        'hdc5puff': 'M19.190388,32.840898 C17.13049,35.649847 15.467793,38.237177 15.562157,41.735917 C15.658087,45.292627 17.130489,48.173097 19.19039,50.701157 M19.110917,32.944915 C15.999325,33.980547 12.381975,38.118987 12.48079,41.782737 C12.57672,45.339447 15.997928,49.397947 19.050944,50.601847 M19.115298,32.944915 C22.22689,33.980547 25.84424,38.118987 25.745425,41.782737 C25.649495,45.339447 22.217287,49.397947 19.164271,50.601847 M19.048853,32.840898 C21.108751,35.649847 22.583452,38.096267 22.583452,41.759327 C22.583452,45.317337 21.108752,48.173097 19.048851,50.701157 M19.124369,32.950416 L19.124369,50.529787',
        'dc5bobble': ' M37.435782,99.271841 C35.375884,102.08079 33.713187,104.66812 33.807551,108.16686 C33.903481,111.72357 35.375883,114.60404 37.435784,117.1321 M37.356311,99.375858 C34.244719,100.41149 30.627369,104.54993 30.726184,108.21368 C30.822114,111.77039 34.253322,115.82889 37.306338,117.03279 M37.360692,99.375858 C40.472284,100.41149 44.089634,104.54993 43.990819,108.21368 C43.894889,111.77039 40.462681,115.82889 37.409665,117.03279 M37.294247,99.271841 C39.354145,102.08079 40.828846,104.52721 40.828846,108.19027 C40.828846,111.74828 39.354146,114.60404 37.294245,117.1321 M37.369763,99.381359 L37.369763,116.96073 M28.564143,108.17104 H46.175382',
        'dc4bobble': 'M49.741665,106.3441 H65.01211 M57.450723,97.428316 C56.217456,100.24248 55.221996,102.83461 55.278491,106.33985 C55.335921,109.90316 56.217455,112.78898 57.450724,115.32173 M57.304447,97.428316 C58.537714,100.24248 59.533174,102.83461 59.476678,106.33985 C59.419248,109.90316 58.535715,112.78898 57.304446,115.32173 M57.365224,97.548915 C54.667209,98.584543 51.530658,102.72299 51.616338,106.38673 C51.699518,109.94345 54.674668,114.00194 57.321893,115.20605 M57.369022,97.548915 C60.067038,98.584543 63.203588,102.72299 63.117908,106.38673 C63.034728,109.94345 59.975578,114.00194 57.323468,115.20605',
        'dc3bobble': 'M70.674659,106.47777 H80.208562 M75.50763,97.578573 C73.447732,100.38753 71.785035,102.97485 71.879399,106.47359 C71.975329,110.0303 73.447731,112.91078 75.507632,115.43881 M75.366095,97.578573 C77.425993,100.38753 78.900694,102.83394 78.900694,106.497 C78.900694,110.05501 77.425994,112.91078 75.366093,115.43881 M75.441611,97.688091 L75.441611,115.26746',
        'tr4bobble': 'M120.76981,152.18047C120.4435,152.92505,120.18012,153.61089,120.19507,154.53831C120.21027,155.48111,120.4435,156.24465,120.76981,156.91477M120.76981,152.18047C121.09611,152.92505,121.35949,153.61089,121.34454,154.53831C121.32934,155.48111,121.09344,156.24465,120.76981,156.91477M120.76981,152.18047C120.05596,152.4545,119.2261,153.54946,119.24877,154.51883C119.27077,155.45988,120.05795,156.53369,120.76981,156.91477M120.76981,152.18047C121.48366,152.4545,122.31354,153.54946,122.29087,154.51883C122.26887,155.45988,121.48168,156.53369,120.76981,156.91477M118.92313,154.15014L119.55729,154.51613M118.92313,154.58103L119.55729,154.94702M121.93807,154.15014L122.57223,154.51613M121.93807,154.58103L122.57223,154.94702M119.88142,154.15014L120.51558,154.51613M119.88142,154.58103L120.51558,154.94702M120.97978,154.15014L121.61394,154.51613M120.97978,154.58103L121.61394,154.94702',
        'dc3pc': 'M58.109607,138.62086 C60.169505,141.42981 60.81661,142.7507 60.81661,146.41376 C60.81661,149.97177 59.34191,152.82753 57.282009,155.35559 M56.583773,138.62086 C54.523875,141.42981 53.87677,142.7507 53.87677,146.41376 C53.87677,149.97177 55.35147,152.82753 57.408374,155.35559 M57.357527,138.69728 L57.357527,155.18422 M54.829525,137.92386 A2.5279996,0.77349651 0 0 1 57.357525,137.15036 A2.5279996,0.77349651 0 0 1 59.885525,137.92386 A2.5279996,0.77349651 0 0 1 57.357525,138.69736 A2.5279996,0.77349651 0 0 1 54.829525,137.92386 M52.590575,146.39453 H62.124478',
        'dc4pc': 'M41.440797,138.61782 C42.392682,140.55473 43.139863,142.76617 43.083367,146.27141 C43.025937,149.83472 42.144404,152.72054 40.911135,155.25329 M40.42111,138.61782 C39.469225,140.55473 38.722044,142.76617 38.77854,146.27141 C38.83597,149.83472 39.717503,152.72054 40.950772,155.25329 M42.568539,138.44048 C44.422407,139.98922 46.781017,142.65455 46.695337,146.31829 C46.612157,149.87501 43.637007,153.9335 40.989783,155.13741 M39.291645,138.44048 C37.437777,139.98922 35.079167,142.65455 35.164847,146.31829 C35.248027,149.87501 38.223177,153.9335 40.870401,155.13741 M33.348354,146.27566 H48.618799 M38.455578,137.86507 A2.5279996,0.77349651 0 0 1 40.983578,137.09157 A2.5279996,0.77349651 0 0 1 43.511578,137.86507 A2.5279996,0.77349651 0 0 1 40.983578,138.63857 A2.5279996,0.77349651 0 0 1 38.455578,137.86507',
        'dc5pc': 'M22.879128,140.19294 C25.527266,142.22169 27.696323,144.48149 27.597508,148.14524 C27.501578,151.70195 24.07037,155.76045 21.017354,156.96435 M19.075978,140.19294 C16.42784,142.22169 14.258783,144.48149 14.357598,148.14524 C14.453528,151.70195 17.884736,155.76045 20.937752,156.96435 M21.728532,140.32893 C23.78843,143.13788 24.435535,144.45877 24.435535,148.12183 C24.435535,151.67984 22.960835,154.5356 20.900934,157.06366 M20.202698,140.32893 C18.1428,143.13788 17.495695,144.45877 17.495695,148.12183 C17.495695,151.67984 18.970395,154.5356 21.028299,157.06366 M20.976452,140.40535 L20.976452,156.89229 M12.170832,148.1026 H29.782071 M18.448452,139.63193 A2.5279996,0.77349651 0 0 1 20.976452,138.85843 A2.5279996,0.77349651 0 0 1 23.504452,139.63193 A2.5279996,0.77349651 0 0 1 20.976452,140.40543 A2.5279996,0.77349651 0 0 1 18.448452,139.63193'
    };
    const hasTopBar = {
        'ring': false,
        'ch': false,
        'ss': false,
        'sc': false,
        'hdc': true,
        'dc': true,
        'tr': true,
        'dtr': true,
        'trtr': true,
        'rsc': false,
        'scbl': false,
        'scfl': false,
        'hdcfl': true,
        'dcfl': true,
        'trfl': true,
        'dtrfl': true,
        'trtrfl': true,
        'hdcbl': true,
        'dcbl': true,
        'trbl': true,
        'dtrbl': true,
        'trtrbl': true,
        'rscfl': false,
        'rscbl': false,
        'fphdc': true,
        'fpdc': true,
        'fptr': true,
        'bphdc': true,
        'bpdc': true,
        'bptr': true,
        'bpsc': false,
        'fpsc': false,
        'line': false,
        'longsc': false,
        'longdc': true,
        'longtr': true,
        'hdc3puff': true,
        'hdc4puff': true,
        'hdc5puff': true,
        'dc5bobble': true,
        'dc4bobble': true,
        'dc3bobble': true,
        'tr4bobble': true,
        'dc3pc': false,
        'dc4pc': false,
        'dc5pc': false
    };
    const recenterInX = {
        'ring': true,
        'ch': true,
        'ss': true,
        'sc': true,
        'hdc': true,
        'dc': true,
        'tr': true,
        'dtr': true,
        'trtr': true,
        'rsc': true,
        'scbl': true,
        'scfl': true,
        'hdcfl': true,
        'dcfl': true,
        'trfl': true,
        'dtrfl': true,
        'trtrfl': true,
        'hdcbl': true,
        'dcbl': true,
        'trbl': true,
        'dtrbl': true,
        'trtrbl': true,
        'rscfl': true,
        'rscbl': true,
        'fphdc': true,
        'fpdc': true,
        'fptr': true,
        'bphdc': true,
        'bpdc': true,
        'bptr': true,
        'bpsc': true,
        'fpsc': true,
        'line': true,
        'longsc': true,
        'longdc': true,
        'longtr': true,
        'hdc3puff': true,
        'hdc4puff': true,
        'hdc5puff': true,
        'dc5bobble': true,
        'dc4bobble': true,
        'dc3bobble': true,
        'tr4bobble': true,
        'dc3pc': true,
        'dc4pc': true,
        'dc5pc': true
    };

    function restoreCoordinates(graphData) {
        if (!graphData.originalCoordinates) {
            console.warn("No original coordinates stored. Cannot restore.");
            return;
        }

        graphData.objects.forEach((obj, i) => {
            if (graphData.originalCoordinates.objects[i]) {
                obj.pos = [...graphData.originalCoordinates.objects[i]];
            }
        });

        graphData.edges.forEach((edge, i) => {
            if (graphData.originalCoordinates.edges[i]) {
                edge.start = [...graphData.originalCoordinates.edges[i].start];
                edge.end = [...graphData.originalCoordinates.edges[i].end];
            }
        });

        delete graphData.originalCoordinates;
    }

    function applyRotation(graphData, objectData) {
        graphData.originalCoordinates = {
            objects: [],
            edges: []
        };
        console.log(graphData, objectData, objectData[0].tx, objectData[0].com);

        function rotatePoint(point, quaternion, com, translation) {
            // Subtract center of mass
            let x = point[0] - com.x;
            let y = point[1] - com.y;
            let z = point[2] - com.z;

            const qx = quaternion.x,
                qy = quaternion.y,
                qz = quaternion.z,
                qw = quaternion.w;

            // Calculate rotation
            const ix = qw * x + qy * z - qz * y;
            const iy = qw * y + qz * x - qx * z;
            const iz = qw * z + qx * y - qy * x;
            const iw = -qx * x - qy * y - qz * z;

            // Apply rotation
            x = ix * qw + iw * -qx + iy * -qz - iz * -qy;
            y = iy * qw + iw * -qy + iz * -qx - ix * -qz;
            z = iz * qw + iw * -qz + ix * -qy - iy * -qx;

            // Add translation and center of mass back
            return [
                x + translation[0] + com.x,
                y + translation[1] + com.y,
                z + translation[2] + com.z
            ];
        }

        graphData.objects.forEach((obj, i) => {
            const objectValue = obj.objectValue;
            const data = objectData[objectValue];

            if (data && data.quaternion) {
                graphData.originalCoordinates.objects.push([...obj.pos]);
                obj.pos = rotatePoint(obj.pos, data.quaternion, data.com, [data.tx, data.ty, data.tz]);
            } else {
                graphData.originalCoordinates.objects.push(null);
            }
        });

        graphData.edges.forEach((edge, i) => {
            const objectValue = edge.objectValue;
            const data = objectData[objectValue];

            if (data && data.quaternion) {
                graphData.originalCoordinates.edges.push({
                    start: [...edge.start],
                    end: [...edge.end]
                });
                edge.start = rotatePoint(edge.start, data.quaternion, data.com, [data.tx, data.ty, data.tz]);
                edge.end = rotatePoint(edge.end, data.quaternion, data.com, [data.tx, data.ty, data.tz]);
            } else {
                graphData.originalCoordinates.edges.push(null);
            }
        });
    }

    function saveSvg(rotateAndSave = false) {
        let size;
        if (c_was_pressed) {
            c_was_pressed = false;
            for (let i = 0; i < NODES.length; i++) {
                NODES[i].material = originalMaterials[i];
                NODES[i].visible = true;
            }
            for (let i = 0; i < NODEShidden.length; i++) {
                NODEShidden[i].visible = true;
            }
            RESETCOLORS = true;
            HIDE = str.objects.length - 1;

            ScaleRadii(1 / factor_radius); // show all radii as normal;
            factor_radius = 1;
            dispatchMyEvent([c_was_pressed, factor_radius, requestedInfo]);
        }

        function tightenAndCenterBBox(draw, svgPath, nodeId) {
            //console.log('ok1');
            const tempPath = draw.path(svgPath);
            //console.log('ok2');
            const bbox = tempPath.bbox();
            //console.log('ok3');
            tempPath.remove();
            //console.log('ok4');

            let centerX = 0.0;
            //console.log(nodeId);
            if (recenterInX[nodeId])
                centerX = bbox.x + bbox.width / 2;
            const centerY = bbox.y + bbox.height / 2;
            //console.log(centerX, centerY);

            const centeredPath = svgPath.replace(/([MLHVCSQTAZ])([^MLHVCSQTAZ]*)/g, (match, cmd, args) => {
                if (cmd === 'Z') return cmd;
                const coords = args.trim().split(/[\s,]+/).map(parseFloat);
                switch (cmd.toUpperCase()) {
                    case 'A':
                        coords[5] -= centerX;
                        coords[6] -= centerY;
                        break;
                    case 'V':
                        coords[0] -= centerY;
                        break;
                    case 'H':
                        coords[0] -= centerX;
                        break;
                    default:
                        for (let i = 0; i < coords.length; i++) {
                            coords[i] -= (i % 2 === 0) ? centerX : centerY;
                        }
                }
                return cmd + coords.join(',');
            });
            //console.log(centeredPath);
            return centeredPath;
        }

        function scalePathData(pathData, scaleX, scaleY) {
            return pathData.replace(/([MLHVCSQTAZ])([^MLHVCSQTAZ]*)/g, (match, cmd, args) => {
                if (cmd === 'Z') return cmd;
                const coords = args.trim().split(/[\s,]+/).map(parseFloat);
                switch (cmd.toUpperCase()) {
                    case 'A':
                        coords[0] *= scaleX;
                        coords[1] *= scaleY;
                        coords[5] *= scaleX;
                        coords[6] *= scaleY;
                        break;
                    case 'V':
                        coords[0] *= scaleY;
                        break;
                    case 'H':
                        coords[0] *= scaleX;
                        break;
                    default:
                        for (let i = 0; i < coords.length; i++) {
                            coords[i] *= (i % 2 === 0) ? scaleX : scaleY;
                        }
                }
                return cmd + coords.join(',');
            });
        }

        function addCrochetSymbolsBetweenNodes(draw, nodes, edges) {


            nodes.forEach(node => {
                let name = node.name.split('|')[0];
                let vis = false;
                for (let j = 0; j < NODES.length; j++) {
                    if (name === NODES[j].id0) {
                        // Match found
                        vis = NODES[j].visible;
                        break;
                    }
                }

                if (vis && (node.label.split('|')[0] !== "hidden")) {
                    const nodeId = node.label.split('|')[0];
                    let edge1 = edges.find(edge => edge.head === node._gvid && edge.color === 'blue');
                    let edge2 = edges.find(edge => edge.tail === node._gvid && edge.color === 'blue');
                    //console.log(nodeId);
                    //console.log('1', edge1);
                    //console.log('2', edge2);
                    if (!edge1) edge1 = null;
                    if (!edge2) edge2 = null;
                    if (edge1 !== null || edge2 !== null) {
                        if (nodeId === 'ch' || nodeId === 'ring') {
                            drawChainBetweenEdges(draw, edge1, edge2, size, symbolMap['ch'], nodeId);
                        } else {
                            drawLineBetweenEdges(draw, edge1, edge2, size, 'plum', 1);
                            if (hasTopBar[nodeId]) {
                                //drawParallelLineThroughCenter(draw, edge1, edge2, size, 'black', 1);
                                drawLineBetweenEdges(draw, edge1, edge2, size, 'black', 1);
                            }
                        }
                    }

                    if (nodeId !== 'ch') {
                        const incomingRedEdges = edges.filter(edge =>
                            edge.head === node._gvid && edge.color === 'red'
                        );
                        if (!(['hdc3puff', 'hdc4puff', 'hdc5puff', 'dc3bobble', 'dc4bobble', 'dc5bobble', 'tr4bobble', 'dc3pc', 'dc4pc', 'dc5pc'].includes(nodeId))) {
                            incomingRedEdges.forEach(edge => {
                                let incomingNode = nodes.find(node => edge.tail === node._gvid);
                                const comesFromLine = (incomingNode.label.split('|')[0]) === 'line';
                                incomingNode = incomingNode._gvid;
                                //console.log(0, nodeId);
                                //console.log(1, incomingNode);
                                if (nodeId.endsWith('fl') || nodeId.endsWith('bl')) {
                                    incomingNode = edges.find(edge => edge.head === incomingNode).tail;
                                    //console.log(2, incomingNode);
                                }

                                const symbol = symbolMap[nodeId] || 'M0,-2.5 L0,2.5';
                                //if (nodeId === 'ss') {
                                let end, start;
                                try {
                                    let edge1e = edges.find(edge0 => edge0.head === edge.head);
                                    let edge2e = edges.find(edge0 => edge0.tail === edge.head);
                                    end = edge2e.start.map((coord, i) => (2 * coord + edge1e.start[i] + edge2e.end[i]) / 4);
                                    try {
                                        let edge1s = edges.find(edge0 => edge0.head === incomingNode);
                                        let edge2s = edges.find(edge0 => edge0.tail === incomingNode);
                                        start = edge.start;
                                        //console.log(edge1s, edge2s);
                                        //console.log(1, start, edge1s, edge2s);
                                        if (['red', 'blue'].includes(edge2s.color) && ['red', 'blue'].includes(edge1s.color)) {
                                            start = edge2s.start.map((coord, i) => (2 * coord + edge1s.start[i] + edge2s.end[i]) / 4);
                                            //console.log(2, start);
                                        }
                                    } catch (error) {
                                        start = edge.start;
                                    }

                                    //let start = edge2.start.map((coord, i) => (2 * coord + edge1.start[i] + edge2.end[i]) / 4);
                                    //console.log(end, edge.end);
                                    drawSymbolAlongEdge(draw, start, end, symbol, size, false, nodeId, comesFromLine);
                                } catch (error) {
                                    drawSymbolAlongEdge(draw, edge.start, edge.end, symbol, size, false, nodeId, comesFromLine);
                                }
                                //} else
                                //    drawSymbolAlongEdge(draw, edge.start, edge.end, symbol, size, false, nodeId, comesFromLine);
                            });
                        } else {
                            //console.log(incomingRedEdges);

                            function findRedPathsWithoutBlue(currentTail, visited = new Set()) {
                                if (visited.has(currentTail)) {
                                    return [];
                                }
                                visited.add(currentTail);

                                const incomingBlueEdges = edges.filter(edge =>
                                    edge.head === currentTail && edge.color === 'blue'
                                );

                                if (incomingBlueEdges.length > 0) {
                                    return [currentTail];
                                }

                                const incomingRedEdges = edges.filter(edge =>
                                    edge.head === currentTail && edge.color === 'red'
                                );

                                let results = [];
                                for (const redEdge of incomingRedEdges) {
                                    const subPaths = findRedPathsWithoutBlue(redEdge.tail, new Set(visited));
                                    results = results.concat(subPaths);
                                }

                                if (results.length === 0) {
                                    results.push(currentTail);
                                }

                                return results;
                            }

                            const redPathsWithoutBlue = incomingRedEdges.flatMap(edge =>
                                findRedPathsWithoutBlue(edge.tail)
                            );

                            const smallestTail = Math.min(...redPathsWithoutBlue);
                            //console.log("Smallest tail of red paths without blue:", smallestTail);

                            // Find the edge with the smallest tail
                            const edgeWithSmallestTail = edges.find(edge => edge.tail === smallestTail && edge.color === 'red');

                            if (edgeWithSmallestTail) {
                                //console.log("Start point of edge with smallest tail:", edgeWithSmallestTail.start);

                                const symbol = symbolMap[nodeId] || 'M0,-2.5 L0,2.5';
                                try {
                                    let edge1e = edges.find(edge0 => edge0.head === incomingRedEdges[0].head);
                                    let edge2e = edges.find(edge0 => edge0.tail === incomingRedEdges[0].head);
                                    let end = edge2e.start.map((coord, i) => (2 * coord + edge1e.start[i] + edge2e.end[i]) / 4);
                                    let edge1s = edges.find(edge0 => edge0.head === edgeWithSmallestTail.tail);
                                    let edge2s = edges.find(edge0 => edge0.tail === edgeWithSmallestTail.tail);
                                    let start = edge2s.start.map((coord, i) => (2 * coord + edge1s.start[i] + edge2s.end[i]) / 4);
                                    drawSymbolAlongEdge(draw, start, end, symbol, size, false, nodeId, false);
                                } catch (error) {
                                    drawSymbolAlongEdge(draw, edgeWithSmallestTail.start, incomingRedEdges[0].end, symbol, size, false, nodeId, false);
                                    //return edgeWithSmallestTail.start; // Return edge.start for the smallest tail
                                }
                            } else {
                                //console.log("No edge found with the smallest tail");
                                //return null; // or some default value
                            }
                        }
                    }
                }
            });
        }

        function drawChainBetweenEdges(draw, edge1, edge2, size, symbolPath, nodeId) {
            let x1, y1, x2, y2;
            //console.log(edge1, edge2, nodeId, size);
            // Calculate average points
            let avgPoint1, avgPoint2;
            if (edge1 === null) {
                avgPoint1 = edge2.start.map((coord, i) => coord - (edge2.end[i] - edge2.start[i]) / 2);
            } else {
                avgPoint1 = edge1.start.map((coord, i) => (coord + edge1.end[i]) / 2);
            }
            if (edge2 === null) {
                avgPoint2 = edge1.end.map((coord, i) => coord + (edge1.end[i] - edge1.start[i]) / 2);
            } else {
                avgPoint2 = edge2.start.map((coord, i) => (coord + edge2.end[i]) / 2);

            }
            if (Dimen == 2) {
                x1 = (avgPoint1[0]) * size / 2.0;
                y1 = (-avgPoint1[1]) * size / 2.0;
                x2 = (avgPoint2[0]) * size / 2.0;
                y2 = (-avgPoint2[1]) * size / 2.0;
            } else {
                x1 = (avgPoint1[0] * xR + avgPoint1[1] * yR + avgPoint1[2] * zR) * size / 2.0;
                y1 = (avgPoint1[0] * xU + avgPoint1[1] * yU + avgPoint1[2] * zU) * size / 2.0;
                x2 = (avgPoint2[0] * xR + avgPoint2[1] * yR + avgPoint2[2] * zR) * size / 2.0;
                y2 = (avgPoint2[0] * xU + avgPoint2[1] * yU + avgPoint2[2] * zU) * size / 2.0;
            }

            const angle = Math.atan2(y2 - y1, x2 - x1);
            const edgeLength = Math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2);
            //console.log(symbolPath);

            let centeredPath = tightenAndCenterBBox(draw, symbolPath, 'ch');
            //console.log(centeredPath);

            const tempPath = draw.path(centeredPath);
            const symbolBBox = tempPath.bbox();
            tempPath.remove();

            let scaleY = edgeLength * 0.93 / symbolBBox.height;
            let scaleX = scaleY / 4;
            if (nodeId === 'ring') {
                scaleY *= 0.5;
                scaleX = scaleY;
            }


            const symbol = draw.path(centeredPath)
                .fill('none')
                .stroke({
                    color: 'black',
                    width: 1
                });

            const scaledPath = scalePathData(centeredPath, scaleX, scaleY);
            symbol.plot(scaledPath);

            const centerX = (x1 + x2) / 2;
            const centerY = (y1 + y2) / 2;

            symbol.transform({
                translateX: centerX,
                translateY: centerY,
                rotate: (angle + Math.PI / 2.) * 180 / Math.PI,
                originX: 'center',
                originY: 'center'
            });
        }

        function drawParallelLineThroughCenter(draw, edge1, edge2, size, lineColor = 'blue', lineWidth = 1) {
            let x0, y0, x1, y1, x2, y2;
            let avgPoint1, avgPoint2, avgPoint0;
            if (edge1 === null) {
                avgPoint1 = edge2.start.map((coord, i) => coord - (edge2.end[i] - edge2.start[i]) / 2);
            } else {
                avgPoint1 = edge1.start.map((coord, i) => (coord + edge1.end[i]) / 2);
            }
            if (edge2 === null) {
                avgPoint2 = edge1.end.map((coord, i) => coord + (edge1.end[i] - edge1.start[i]) / 2);
                avgPoint0 = edge1.end;
            } else {
                avgPoint2 = edge2.start.map((coord, i) => (coord + edge2.end[i]) / 2);
                avgPoint0 = edge2.start;
            }
            // Calculate average points for the original line

            // Transform points
            if (Dimen == 2) {
                x0 = (avgPoint0[0]) * size / 2.0;
                y0 = (-avgPoint0[1]) * size / 2.0;
                x1 = (avgPoint1[0]) * size / 2.0;
                y1 = (-avgPoint1[1]) * size / 2.0;
                x2 = (avgPoint2[0]) * size / 2.0;
                y2 = (-avgPoint2[1]) * size / 2.0;
            } else {
                x0 = (avgPoint0[0] * xR + avgPoint0[1] * yR + avgPoint0[2] * zR) * size / 2.0;
                y0 = (avgPoint0[0] * xU + avgPoint0[1] * yU + avgPoint0[2] * zU) * size / 2.0;
                x1 = (avgPoint1[0] * xR + avgPoint1[1] * yR + avgPoint1[2] * zR) * size / 2.0;
                y1 = (avgPoint1[0] * xU + avgPoint1[1] * yU + avgPoint1[2] * zU) * size / 2.0;
                x2 = (avgPoint2[0] * xR + avgPoint2[1] * yR + avgPoint2[2] * zR) * size / 2.0;
                y2 = (avgPoint2[0] * xU + avgPoint2[1] * yU + avgPoint2[2] * zU) * size / 2.0;
            }

            // Calculate the direction vector of the original line
            const dx = x2 - x1;
            const dy = y2 - y1;

            // Calculate the length of the line
            const lineLength = Math.sqrt(dx * dx + dy * dy);

            // Calculate the start and end points of the parallel line
            const halfLength = lineLength * 0.8 / 2;
            const unitDx = dx / lineLength;
            const unitDy = dy / lineLength;

            const startX = x0 - halfLength * unitDx;
            const startY = y0 - halfLength * unitDy;
            const endX = x0 + halfLength * unitDx;
            const endY = y0 + halfLength * unitDy;

            // Draw the parallel line
            draw.line(startX, startY, endX, endY)
                .stroke({
                    color: lineColor,
                    width: lineWidth
                });
        }

        function drawLineBetweenEdges(draw, edge1, edge2, size, lineColor = 'green', lineWidth = 1) {
            let x1, y1, x2, y2;

            // Calculate average points
            let avgPoint1, avgPoint2;
            if (edge1 === null) {
                avgPoint1 = edge2.start.map((coord, i) => coord - (edge2.end[i] - edge2.start[i]) / 2);
            } else {
                avgPoint1 = edge1.start.map((coord, i) => (coord + edge1.end[i]) / 2);
            }
            if (edge2 === null) {
                avgPoint2 = edge1.end.map((coord, i) => coord + (edge1.end[i] - edge1.start[i]) / 2);

            } else {
                avgPoint2 = edge2.start.map((coord, i) => (coord + edge2.end[i]) / 2);

            }

            if (Dimen == 2) {
                x1 = (avgPoint1[0]) * size / 2.0;
                y1 = (-avgPoint1[1]) * size / 2.0;
                x2 = (avgPoint2[0]) * size / 2.0;
                y2 = (-avgPoint2[1]) * size / 2.0;
            } else {
                x1 = (avgPoint1[0] * xR + avgPoint1[1] * yR + avgPoint1[2] * zR) * size / 2.0;
                y1 = (avgPoint1[0] * xU + avgPoint1[1] * yU + avgPoint1[2] * zU) * size / 2.0;
                x2 = (avgPoint2[0] * xR + avgPoint2[1] * yR + avgPoint2[2] * zR) * size / 2.0;
                y2 = (avgPoint2[0] * xU + avgPoint2[1] * yU + avgPoint2[2] * zU) * size / 2.0;
            }
            if (lineColor === 'black') {
                let x0 = (x1 + x2) / 2.0;
                let y0 = (y1 + y2) / 2.0;
                let dx = x2 - x1;
                let dy = y2 - y1;
                x1 = x0 - dx / 2 * 0.8;
                x2 = x0 + dx / 2 * 0.8;
                y1 = y0 - dy / 2 * 0.8;
                y2 = y0 + dy / 2 * 0.8;
            }
            draw.line(x1, y1, x2, y2)
                .stroke({
                    color: lineColor,
                    width: lineWidth
                });
        }

        function drawSymbolAlongEdge(draw, start, end, symbolPath, size, isChain, nodeId, comesFromLine) {


            let x1, y1, x2, y2;

            if (Dimen == 2) {
                x1 = (start[0]) * size / 2.0;
                y1 = (-start[1]) * size / 2.0;
                x2 = (end[0]) * size / 2.0;
                y2 = (-end[1]) * size / 2.0;
            } else {
                x1 = (start[0] * xR + start[1] * yR + start[2] * zR) * size / 2.0;
                y1 = (start[0] * xU + start[1] * yU + start[2] * zU) * size / 2.0;
                x2 = (end[0] * xR + end[1] * yR + end[2] * zR) * size / 2.0;
                y2 = (end[0] * xU + end[1] * yU + end[2] * zU) * size / 2.0;
            }

            const angle = Math.atan2(y2 - y1, x2 - x1);
            const edgeLength = Math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2);

            let centeredPath = tightenAndCenterBBox(draw, symbolPath, nodeId);

            const tempPath = draw.path(centeredPath);
            const symbolBBox = tempPath.bbox();
            tempPath.remove();

            let scaleY = edgeLength * 0.9 / symbolBBox.height; // Scale to 80% of edge length
            let posted = false;
            if (nodeId.startsWith('fp') || nodeId.startsWith('bp')) {
                scaleY *= 1.1 / 0.9;
                posted = true;
                if (['fpsc', 'bpsc'].includes(nodeId)) {
                    scaleY *= 1.2;
                }
            }
            let scaleX = isChain ? scaleY : 1; // For chain, maintain aspect ratio
            if (['hdc3puff', 'hdc4puff', 'hdc5puff', 'dc3bobble', 'dc4bobble', 'dc5bobble', 'tr4bobble', 'dc3pc', 'dc4pc', 'dc5pc'].includes(nodeId)) {
                scaleX = scaleY / 1.6;
            }
            let fill = 'none';
            if (nodeId === 'ss') {
                fill = 'black';
                scaleY *= 0.4;
                scaleX = scaleY / 1.333;
            }
            const symbol = draw.path(centeredPath)
                .fill(fill)
                .stroke({
                    color: 'black',
                    width: 1
                });
            if (nodeId === 'line' || comesFromLine) {
                scaleY /= 0.9;
                scaleX = scaleY;
            }
            if (nodeId === 'line' && (!comesFromLine)) {
                scaleY *= 0.95;
                scaleX *= 0.95;
            }
            const scaledPath = scalePathData(centeredPath, scaleX, scaleY);
            symbol.plot(scaledPath);

            // Calculate position at 50% of the edge (between 10% and 90%)
            let centerX, centerY;
            if ((nodeId !== 'ss') && (nodeId !== 'line') && (!comesFromLine)) {
                if (!posted) {
                    centerX = x1 + (x2 - x1) * 0.55;
                    centerY = y1 + (y2 - y1) * 0.55;
                } else {
                    if (['fpsc', 'bpsc'].includes(nodeId)) {
                        centerX = x1 + (x2 - x1) * (1 - 1.1 * 1.2 / 2);
                        centerY = y1 + (y2 - y1) * (1 - 1.1 * 1.2 / 2);
                    } else {
                        centerX = x1 + (x2 - x1) * 0.45;
                        centerY = y1 + (y2 - y1) * 0.45;
                    }

                }
            } else {
                if (nodeId === 'line' && (!comesFromLine)) {
                    centerX = x1 + (x2 - x1) * (1.0 - 0.95 / 2.0);
                    centerY = y1 + (y2 - y1) * (1.0 - 0.95 / 2.0);
                } else {
                    centerX = x1 + (x2 - x1) * 0.5;
                    centerY = y1 + (y2 - y1) * 0.5;
                }
            }

            symbol.transform({
                translateX: centerX,
                translateY: centerY,
                rotate: (angle + Math.PI / 2) * 180 / Math.PI,
                originX: 'center',
                originY: 'center'
            });
        }
        //console.log(1, rotateAndSaveSizeSet, rotateAndSave);
        if (rotateAndSaveSizeSet == -1 || (!rotateAndSave)) {
            while (true) {
                try {
                    let s = prompt('Enter the height (in pixels) of the SVG file. This will affect size of labels. Default: 1500');
                    if (s === '')
                        size = 1500;
                    else
                        size = parseInt(s);
                } catch (error) {
                    size = -1;
                }
                if ((size > 50) && (size < 15000))
                    break;
            }
            if (rotateAndSave)
                rotateAndSaveSizeSet = size;
            else
                rotateAndSaveSizeSet = -1;
        } else {
            size = rotateAndSaveSizeSet;
        }
        //console.log(2, rotateAndSaveSizeSet, rotateAndSave);
        //size = 750;
        // Set up camera and coordinate system
        const graphData = str;
        var xC = camera.position.x;
        var yC = camera.position.y;
        var zC = camera.position.z;
        var xU = camera.up.x;
        var yU = camera.up.y;
        var zU = camera.up.z;
        var xR = -(yC * zU - zC * yU);
        var yR = -(-(xC * zU - zC * xU));
        var zR = -(xC * yU - yC * xU);
        var nR = Math.sqrt(xR * xR + yR * yR + zR * zR);
        var nC = Math.sqrt(xC * xC + yC * yC + zC * zC);
        xR /= nR;
        yR /= nR;
        zR /= nR;
        xC /= nC;
        yC /= nC;
        zC /= nC;
        xU = -(yC * zR - zC * yR);
        yU = -(-(xC * zR - zC * xR));
        zU = -(xC * yR - yC * xR);

        applyRotation(graphData, objectData);

        //these need to be rotated.
        //  graphData.objects.pos
        //  graphData.edges.start
        //  graphData.edges.end

        // Create SVG for graph elements
        const drawGraph = SVG().size(size, size);
        const nodes = drawGraph.group();
        const edges = drawGraph.group();

        // Draw nodes
        graphData.objects.forEach(node => {
            let name = node.name.split('|')[0];
            let vis = false;
            for (let j = 0; j < NODES.length; j++) {
                if (name === NODES[j].id0) {
                    // Match found
                    vis = NODES[j].visible;
                    break;
                }
            }

            if (vis && (node.label.split('|')[0] !== "hidden")) {
                var x, y;
                if (Dimen == 2) {
                    x = (node.pos[0]) * size / 2.0;
                    y = (-node.pos[1]) * size / 2.0;
                } else {
                    x = ((node.pos[0] * xR + node.pos[1] * yR + node.pos[2] * zR)) * size / 2.0;
                    y = ((node.pos[0] * xU + node.pos[1] * yU + node.pos[2] * zU)) * size / 2.0;
                }
                const circle = nodes.circle(5).center(x, y).fill('white').stroke('gray');
                var text = nodes.text(node.label.split('|')[0] + '(' + node.name.split('|')[0] + ')').cx(x).cy(y);
                var fontSize = 1.5 * 1.5 * 5;
                text.font({
                    size: fontSize / 1.5 / 1.5
                });
                text.cx(x + circle.bbox().width + text.bbox().width / 2).cy(y);
            }
        });

        // Draw edges
        var arrowhead = drawGraph.marker(17, 3, function(add) {
            add.polygon('0,0 7,1.5 0,3').fill('gray');
        });
        graphData.edges.forEach(edge => {
            const start = edge.start;
            const end = edge.end;
            var x0, y0, x1, y1;
            if (Dimen == 2) {
                x0 = (start[0]) * size / 2.0;
                y0 = (-start[1]) * size / 2.0;
                x1 = (end[0]) * size / 2.0;
                y1 = (-end[1]) * size / 2.0;
            } else {
                x0 = ((start[0] * xR + start[1] * yR + start[2] * zR)) * size / 2.0;
                y0 = ((start[0] * xU + start[1] * yU + start[2] * zU)) * size / 2.0;
                x1 = ((end[0] * xR + end[1] * yR + end[2] * zR)) * size / 2.0;
                y1 = ((end[0] * xU + end[1] * yU + end[2] * zU)) * size / 2.0;
            }

            let name = str.objects[str.objects.findIndex((obj) => obj._gvid === edge.head)].name.split('|')[0];
            let vis = false;
            for (let j = 0; j < NODES.length; j++) {
                if (name === NODES[j].id0) {
                    // Match found
                    vis = NODES[j].visible;
                    break;
                }
            }
            if (vis) {
                let line;
                if (edge.gray == 1)
                    line = edges.line(x0, y0, x1, y1).stroke({
                        color: 'gray',
                        width: 0.2
                    });
                else
                    line = edges.line(x0, y0, x1, y1).stroke(edge.color).marker('end', arrowhead);

                edge.type = edge.label || 'ch';
            }
        });

        // Save graph SVG

        console.log(graphData);
        saveSVGToFile(drawGraph, 'graph.svg', size);
        addCrochetSymbolsBetweenNodes(drawGraph, graphData.objects, graphData.edges);
        saveSVGToFile(drawGraph, 'graph_with_std_crochet_symbols.svg', size);

        // Create SVG for crochet symbols
        const drawSymbols = SVG().size(size, size);
        addCrochetSymbolsBetweenNodes(drawSymbols, graphData.objects, graphData.edges);

        // Save crochet symbols SVG
        saveSVGToFile(drawSymbols, 'crochet_symbols.svg', size);
        restoreCoordinates(graphData);

    }

    function adjustSVGToSymmetricBBox(draw) {
        // Get the current bounding box of all elements
        const bbox = draw.bbox();

        // Calculate the maximum extent in each direction to make it symmetric
        const maxExtentX = Math.max(Math.abs(bbox.x), Math.abs(bbox.x2));
        const maxExtentY = Math.max(Math.abs(bbox.y), Math.abs(bbox.y2));

        // Define a new symmetric bounding box centered at (0, 0)
        const newWidth = maxExtentX * 2; // Total width
        const newHeight = maxExtentY * 2; // Total height
        const newX = -maxExtentX; // Start x-coordinate
        const newY = -maxExtentY; // Start y-coordinate

        // Set the viewBox to the new symmetric bounding box
        draw.viewbox(newX, newY, newWidth, newHeight);

        // Resize the SVG element to match the new dimensions
        draw.size(newWidth, newHeight);
    }

    function saveSVGToFile(draw, filename) {
        //const bbox = draw.bbox();
        //console.log(draw.bbox());
        adjustSVGToSymmetricBBox(draw);
        //console.log(draw.bbox());
        // Update the viewBox of the SVG to fit all elements
        //draw.viewbox(bbox.x, bbox.y, bbox.width, bbox.height);
        const svgData = draw.svg();
        const blob = new Blob([svgData], {
            type: 'image/svg+xml'
        });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        a.click();
        URL.revokeObjectURL(url);
    }





    function exportGLTF() {
        var input = scene1;
        if (scene1 == null || (scene1.children.length == 0)) {
            alert('Re-run model by pressing "Show model in 3D".');
            return;
        }
        const link = document.createElement('a');
        link.style.display = 'none';
        document.body.appendChild(link); // Firefox workaround, see #6594
        function save(blob, filename) {

            link.href = URL.createObjectURL(blob);
            link.download = filename;
            link.click();

            // URL.revokeObjectURL( url ); breaks Firefox...

        }

        function saveString(text, filename) {

            save(new Blob([text], {
                type: 'text/plain'
            }), filename);

        }
        const gltfExporter = new GLTFExporter();

        //const options = {
        //    trs: params.trs,
        //    onlyVisible: params.onlyVisible,
        //    binary: params.binary,
        //    maxTextureSize: params.maxTextureSize
        //};
        //for (let i of NODES)
        //    if ('is_arrow' in i)
        //        i.visible = false
        gltfExporter.parse(
            input,
            function(result) {

                if (result instanceof ArrayBuffer) {

                    saveArrayBuffer(result, 'scene.glb');

                } else {

                    const output = JSON.stringify(result, null, 2);
                    //console.log(output);
                    saveString(output, 'scene.gltf');

                }

            },
            function(error) {

                console.log('An error happened during parsing', error);

            } //,
            //options
        );
        //while (scene1.children.length > 0) {
        //    scene1.remove(scene1.children[0]);
        // }
        //link.parentNode.removeChild(link);
    }
    //exportGLTF(scene);

    const objectInput = document.getElementById('objectInput');
    objectInput.max = maxObjects; // Set the new max value
    objectInput.dispatchEvent(new Event('input', {
        bubbles: true
    }));
    // Object to store transformations and COM for each object value
    const objectData = {};
    var allNodes = [...NODES, ...NODEShidden, ...NODES1];

    function initializeObjectData(objectValue) {
        if (objectValue === -1) {
            // Check for all existing #TRANSFORM_OBJECT: entries
            const allTransformsRegex = /#TRANSFORM_OBJECT: (\d+),(-?[\d.]+),(-?[\d.]+),(-?[\d.]+),(-?[\d.]+),(-?[\d.]+),(-?[\d.]+)/g;
            let match;
            let currentText = inputText.value;
            updateObjectData(0, 0, 0, 0, 0, 0, 0);
            while ((match = allTransformsRegex.exec(currentText)) !== null) {
                let [, objValueStr, tx, ty, tz, rx, ry, rz] = match;
                const objValue = parseInt(objValueStr, 10);
                [tx, ty, tz, rx, ry, rz] = [tx, ty, tz, rx, ry, rz].map(parseFloat);
                updateObjectData(objValue, tx, ty, tz, rx, ry, rz);
            }
        } else {
            // Original logic for specific objectValue
            const regex = new RegExp(`#TRANSFORM_OBJECT: ${objectValue},(-?\\d+(\\.\\d+)?),(-?\\d+(\\.\\d+)?),(-?\\d+(\\.\\d+)?),(-?\\d+(\\.\\d+)?),(-?\\d+(\\.\\d+)?),(-?\\d+(\\.\\d+)?)`, 'g');
            const match = inputText.value.match(regex);
            //console.log('none0:', objectData[objectValue]);
            if (match) {
                const [, tx, , ty, , tz, , rx, , ry, , rz] = match[0].split(',').map(parseFloat);
                updateObjectData(objectValue, tx, ty, tz, rx, ry, rz);
            } else if (!(objectValue in objectData)) {
                //console.log('none:', objectData[objectValue]);
                updateObjectData(objectValue, 0, 0, 0, 0, 0, 0);
                //console.log('none2:', objectData[objectValue]);
            }
        }

        //updateTextArea();
    }

    function updateObjectData(objectValue, tx, ty, tz, rx, ry, rz) {

        if (!objectData[objectValue]) {
            const relevantNodes = allNodes.filter(node => node.objectValue === objectValue);
            const com = new THREE.Vector3();
            relevantNodes.forEach(node => com.add(node.position));
            com.divideScalar(relevantNodes.length);

            objectData[objectValue] = {
                tx,
                ty,
                tz,
                rx,
                ry,
                rz,
                quaternion: new THREE.Quaternion().setFromEuler(new THREE.Euler(0, 0, 0)),
                com: com
                //originalPositions: relevantNodes.map(node => node.position.clone().sub(com))
            };
        } else {
            Object.assign(objectData[objectValue], {
                tx,
                ty,
                tz,
                rx,
                ry,
                rz
            });
            //  objectData[objectValue].quaternion = new THREE.Quaternion().setFromEuler(new THREE.Euler(rx, ry, rz));
        }
    }

    function readInstructions() {
        const allTransformsRegex = /#TRANSFORM_OBJECT: (\d+),(-?[\d.]+),(-?[\d.]+),(-?[\d.]+),(-?[\d.]+),(-?[\d.]+),(-?[\d.]+)/g;
        let match;
        let currentText = inputText.value;
        let k = 0;
        while ((match = allTransformsRegex.exec(currentText)) !== null) {
            k++;
            let [, objValueStr, tx, ty, tz, rx, ry, rz] = match;
            const objValue = parseInt(objValueStr, 10);
            [tx, ty, tz, rx, ry, rz] = [tx, ty, tz, rx, ry, rz].map(parseFloat);

            updateObjectData(objValue, tx, ty, tz, rx, ry, rz);
            objectInput.value = objValue;
            objectInput.dispatchEvent(new Event('input', {
                bubbles: true
            }));

            //initializeObjectData(value);
            updateUIFromStoredTransform(objValue);
            updateTransform(objValue);

        }
        if (k == 0) {
            for (let v = 0; v <= objectInput.max; v++) {
                updateObjectData(v, 0, 0, 0, 0, 0, 0);
                updateUIFromStoredTransform(v);
                updateTransform(v);
            }
        } else
            for (let v = 0; v <= parseInt(objectInput.max); v++) {
                if (!objectData[v]) {
                    updateObjectData(v, 0, 0, 0, 0, 0, 0);
                    objectInput.value = v;
                    objectInput.dispatchEvent(new Event('input', {
                        bubbles: true
                    }));
                    updateUIFromStoredTransform(v);
                    updateTransform(v);
                }
            }

        updateUIFromStoredTransform(parseInt(objectInput.value));
    }

    function updateTextArea() {
        // Get existing lines
        let lines = inputText.value.split('\n');
        let transformLines = {};
        let otherLines = [];

        // Separate transform lines and other lines
        lines.forEach(line => {
            if (line.startsWith('#TRANSFORM_OBJECT:')) {
                const [, objValueStr] = line.split(':');
                const objValue = parseInt(objValueStr.split(',')[0].trim(), 10);
                transformLines[objValue] = line;
            } else {
                otherLines.push(line);
            }
        });

        // Update or add transform lines
        Object.keys(objectData).forEach(objValue => {
            if (objValue <= objectInput.max) {
                const data = objectData[objValue];
                transformLines[objValue] = `#TRANSFORM_OBJECT: ${objValue},${data.tx},${data.ty},${data.tz},${data.rx},${data.ry},${data.rz}`;
            }
        });

        // Combine other lines and transform lines
        let updatedLines = otherLines.concat(Object.values(transformLines));

        // Update textarea
        inputText.value = updatedLines.join('\n');
    }


    objectInput.addEventListener('input', function() {
        let value = parseInt(this.value);
        if (isNaN(value)) value = 0;
        value = Math.max(0, Math.min(objectInput.max, value));
        this.value = value;

        //initializeObjectData(value);
        updateUIFromStoredTransform(value);
        //console.log('aha:', objectData[value].tx);
        //console.log('all:', returnTranslation());
        updateTransform(value);
        updateMaterials();
        //console.log('aha1:', objectData[value].tx);


    });

    function updateUIFromStoredTransform(objectValue) {
        //console.log(objectValue);
        //console.log(objectData[objectValue]);
        //console.log(objectData);
        if (objectValue in objectData) {
            //console.log('set!');
            const data = objectData[objectValue];
            //console.log('send:', data.tx);
            setRotationAngles(THREE.MathUtils.radToDeg(data.ry), THREE.MathUtils.radToDeg(-data.rx), THREE.MathUtils.radToDeg(data.rz));
            setTranslationValues(parseFloat(data.tx), parseFloat(data.ty), parseFloat(data.tz));
            //console.log('back:', returnTranslation());
            //console.log(planeMesh);


            gridHelper.position.set(data.tx + data.com.x, data.ty + data.com.y, data.tz + data.com.z + 0.001);
            planeMesh.position.set(data.tx + data.com.x, data.ty + data.com.y, data.tz + data.com.z);

            // Update guidingCylinder position
            guidingCylinder.position.set(
                data.tx + data.com.x,
                data.ty + data.com.y,
                data.tz + data.com.z
            );

            // Align guidingCylinder to be perpendicular to the planeMesh
            const normal = new THREE.Vector3();
            normal.set(0, 0, 1).applyQuaternion(planeMesh.quaternion); // Get normal vector of the plane in world space

            const axis = new THREE.Vector3(0, 1, 0); // Default up direction for the cylinder
            const quaternion = new THREE.Quaternion().setFromUnitVectors(axis, normal); // Compute rotation quaternion

            guidingCylinder.setRotationFromQuaternion(quaternion);

            updateAxesVisualization(data);

        } else {
            setRotationAngles(0, 0, 0);
            setTranslationValues(0, 0, 0);
        }

    }

    function updateTransform(objectValue) {
        if (objectValue == -1)
            objectValue = parseInt(objectInput.value);
        //console.log('aha2:', objectData[objectValue].tx);
        initializeObjectData(objectValue);
        //console.log('aha3:', objectData[objectValue].tx);
        const data = objectData[objectValue];
        //console.log('update:', data.tx);
        let ss = returnTranslation();
        //console.log('update1:', ss[0]);
        data['tx'] = ss[0];
        data['ty'] = ss[1];
        data['tz'] = ss[2];
        //console.log('tx', data.tx);
        let rr = returnRotational();
        data['rx'] = THREE.MathUtils.degToRad(-rr[1]);
        data['ry'] = THREE.MathUtils.degToRad(rr[0]);
        data['rz'] = THREE.MathUtils.degToRad(rr[2]);

        const rotationQuaternion = new THREE.Quaternion().setFromEuler(new THREE.Euler(data.rx, data.ry, data.rz, 'XYZ'));
        const rotationQuaternion0 = data.quaternion.invert();



        const relevantNodes = allNodes.filter(node => node.objectValue === objectValue);
        const com = new THREE.Vector3();
        relevantNodes.forEach(node => com.add(node.position));
        com.divideScalar(relevantNodes.length);
        relevantNodes.forEach((node, index) => {
            // Start from the original position relative to this object's COM

            // Apply rotation
            node.position.sub(com);
            node.position.applyQuaternion(rotationQuaternion0);
            node.position.applyQuaternion(rotationQuaternion);
            node.quaternion.premultiply(rotationQuaternion0);
            node.quaternion.premultiply(rotationQuaternion);
            // Shift back by COM

            // Apply translation and add back the COM
            node.position.add(new THREE.Vector3(data.tx, data.ty, data.tz)).add(data.com);

        });
        data.quaternion.copy(rotationQuaternion);
        updateAxesVisualization(data);

        renderer.render(scene, camera);
        //updateTextArea();
    }



    // Add event listeners to sliders


    // Initialize data for the first object value (assuming it's 0)




    // Initial render
    renderer.render(scene, camera);



    // Render the scene
    function animate() {


        requestAnimationFrame(animate);

        controls.update();

        //console.log(camera.up.x, camera.up.y, camera.up.z, camera.position, camera., XU, YU, ZU)
        if (!wasMouseDown) {

            controls.autoRotate = true; //updateCamera();;
            controls.update();
            //setTimeout(function() {
            //    saveSvg();
            //}, 300);
        } else {
            controls.autoRotate = false; //updateCamera();;
            controls.update();
        }



        renderer.render(scene, camera);
        if ((!wasMouseDown) && rotateAndSave) {

            rotateAndSave = false;
            wasMouseDown = true;
            setTimeout(function() {
                saveSvg(true);

            }, 300);
        }
        //if (rotateAndSave) {
        //    rotateAndSave = false;
        //    wasMouseDown = true;
        //}
        //     rendererSVG.render(scene, camera);
        //     console.log(rendererSVG.domElement.outerHTML);
    }
    animate();

    document.addEventListener('myCustomEvent', function() {
        updateTransform(-1);
        //document.removeEventListener('myCustomEvent', handleMyCustomEvent);
    });

    function updateMaterials() {
        const controlPanel = document.getElementById('controlPanel');

        if (controlPanel.style.display === 'block') {
            for (let i = 0; i < NODES.length; i++)
                NODES[i].material = originalMaterials[i];

            NODES.forEach(node => {
                if (node.objectValue === parseInt(objectInput.value)) {
                    if (node.material) {
                        node.material.dispose(); // Dispose of the old material to free memory
                    }
                    node.material = selectedObjectMaterial;
                }
            });
            ScaleRadii(1 / factor_radius);
            factor_radius = 1.0;
            c_was_pressed = false;
            dispatchMyEvent([c_was_pressed, factor_radius, requestedInfo]);
        }

    }

    const controlPanel = document.getElementById('controlPanel');
    const observer1 = new MutationObserver(mutationsList => {
        mutationsList.forEach(mutation => {
            if (mutation.attributeName === 'style') {
                const currentDisplay = window.getComputedStyle(controlPanel).display;
                const matchResult = mutation.oldValue && mutation.oldValue.match(/display:\s*(\w+)/);
                const previousDisplay = matchResult ? matchResult[1] : 'none';

                // Trigger updateMaterials only when display changes from 'none' to 'block'
                if (previousDisplay === 'none' && currentDisplay === 'block') {
                    updateMaterials();
                }
                if (previousDisplay === 'block' && currentDisplay === 'none') {
                    if (!c_was_pressed) {
                        //c_was_pressed = false;
                        for (let i = 0; i < NODES.length; i++)
                            NODES[i].material = originalMaterials[i];
                        ScaleRadii(1 / factor_radius);
                        factor_radius = 1.0;
                        dispatchMyEvent([c_was_pressed, factor_radius, requestedInfo]);
                    } else {
                        dispatchMyEvent([c_was_pressed, factor_radius, requestedInfo]);
                        showArrows = false;
                        for (let i of NODES) {
                            i.material = new THREE.MeshLambertMaterial({
                                color: new THREE.Color(i.Color)
                            });
                            if (('is_arrow' in i) || i.type == 0)
                                i.visible = false;
                        }
                        for (let i of NODEShidden)
                            i.visible = false;

                    }
                }

            }
        });
    });

    // Observe the controlPanel element for style attribute changes
    observer1.observe(controlPanel, {
        attributes: true,
        attributeOldValue: true,
        attributeFilter: ['style']
    });
    // Start observing changes to the style attribute of controlPanel
    observer1.observe(controlPanel, {
        attributes: true,
        attributeOldValue: true,
        attributeFilter: ['style']
    });

    ScaleRadii(factor_radius);
    if (c_was_pressed) {
        showArrows = false;
        for (let i of NODES) {
            i.material = new THREE.MeshLambertMaterial({
                color: new THREE.Color(i.Color)
            });
            if (('is_arrow' in i) || i.type == 0)
                i.visible = false;
        }
        for (let i of NODEShidden)
            i.visible = false;
    }

    return [renderer, scene, onMouseDown, onMove, handleKeyDown, handleKeyUp, STATS, handleKeyDownHide, handleKeyDownHideAnim, exportGLTF, scene1, saveSvg, readInstructions, updateTextArea];
}