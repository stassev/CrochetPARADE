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
//import {
//    SVGRenderer
//} from 'three/addons/renderers/SVGRenderer.js'
export default function Generate3DModel(json0, renderer, scene, scene1, backgroundColor) {



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


    var str = JSON.parse(JSON.stringify(json0)); //JSON.parse(json0);
    //console.log(str)
    // Create a scene
    scene = new THREE.Scene();
    scene1 = new THREE.Scene();

    //set background color
    if (backgroundColor === '')
        scene.background = new THREE.Color("rgb(210, 210, 210)");
    else
        scene.background = new THREE.Color(backgroundColor);


    // Create a camera




    // Create a renderer

    const domElement = document.querySelector('canvas');
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


    // Create a geometry for the nodes
    const nodeGeometry = new THREE.SphereGeometry(0.006, 8, 4);

    // Create a material for the nodes
    const nodeMaterial = new THREE.MeshLambertMaterial({
        color: new THREE.Color(0.9, 0, 0.9)
    });

    const selectedNodeMaterial = new THREE.MeshBasicMaterial({
        color: new THREE.Color(0, 0.8, 0)
    });

    var NODES = [];
    var NODEShidden = [];
    var NODES1 = [];
    // Create the nodes
    str.objects.forEach((obj) => {
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
            scene.add(node);
            NODES.push(node);
        }
    });

    //Find average edge scaling factor
    var lenF = 0.0,
        totLen = 0.0;
    for (let edge of str.edges) {
        edge['Color'] = edge.label;

        const tail = str.objects.find((obj) => obj._gvid === edge.tail);
        const head = str.objects.find((obj) => obj._gvid === edge.head);

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

            // Add the line to the scene
            scene1.add(line1);
            NODES1.push(line1);
        }
        ///



        if (!(non)) {
            NODES.push(line);
            NODES.push(arrowhead);
        } else
            NODEShidden.push(line);

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
    var requestedInfo = true;

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

    var c_was_pressed = false;
    var factor_radius = 1.0;

    var RESETCOLORS = true;
    var HIDE = str.objects.length - 1;

    //Search and highlight
    function handleKeyDown(event) {
        if (canvasClicked && (event.key === 'i')) {
            requestedInfo = !requestedInfo;
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
        if (canvasClicked && (event.key === 'p')) {
            setTimeout(function() {
                saveSvg();
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



    function saveSvg() {
        var size;
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

        const draw = SVG().size(size, size);
        const nodes = draw.group();
        const edges = draw.group();
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
        //r-(r.hatrC)hatC
        var k = -1;
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
                    x = (node.pos[0] + 1) * size / 2.0;
                    y = (-node.pos[1] + 1) * size / 2.0;
                } else {
                    x = node.pos[0] * xR + node.pos[1] * yR + node.pos[2] * zR;
                    y = node.pos[0] * xU + node.pos[1] * yU + node.pos[2] * zU;
                    x = (x + 1) * size / 2.0;
                    y = (y + 1) * size / 2.0;
                }
                const circle = nodes.circle(5).center(x, y).fill('white').stroke('gray');
                var text = nodes.text(node.label.split('|')[0] + '(' + node.name.split('|')[0] + ')').cx(x).cy(y); //node.id0

                //text.font({
                //    size: fontSize
                //});
                //while (text.bbox().width < circle.bbox().width && text.bbox().height < circle.bbox().height) {
                //    text.font({
                //        size: fontSize
                //    });
                //    fontSize *= 1.5;
                //}
                var fontSize = 1.5 * 1.5 * 5;
                text.font({
                    size: fontSize / 1.5 / 1.5
                });
                //text.cx(x + text.bbox().width / 2. - 0 * circle.bbox().width / 2.).cy(y - text.bbox().height / 2. + 0 * circle.bbox().height / 2.)
                text.cx(x + circle.bbox().width + text.bbox().width / 2).cy(y);
            }
        });

        var arrowhead = draw.marker(17, 3, function(add) {
            add.polygon('0,0 7,1.5 0,3').fill('gray');
        });
        graphData.edges.forEach(edge => {
            const start = edge.start;
            const end = edge.end;
            var x0, y0, x1, y1;
            if (Dimen == 2) {
                x0 = start[0];
                y0 = -start[1];
                x1 = end[0];
                y1 = -end[1];
            } else {
                x0 = start[0] * xR + start[1] * yR + start[2] * zR;
                y0 = start[0] * xU + start[1] * yU + start[2] * zU;
                x1 = end[0] * xR + end[1] * yR + end[2] * zR;
                y1 = end[0] * xU + end[1] * yU + end[2] * zU;
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
                if (edge.gray == 1)
                    edges.line((x0 + 1) * size / 2.0, (y0 + 1) * size / 2.0, (x1 + 1) * size / 2.0, (y1 + 1) * size / 2.0).stroke({
                        color: 'gray',
                        width: 0.2
                    }); //.marker('end', arrowhead);;
                else
                    edges.line((x0 + 1) * size / 2.0, (y0 + 1) * size / 2.0, (x1 + 1) * size / 2.0, (y1 + 1) * size / 2.0).stroke(edge.color).marker('end', arrowhead);
            }
        });

        // Render the graph
        draw.add(nodes, edges);

        // Save the SVG file
        const svgData = draw.svg();
        const blob = new Blob([svgData], {
            type: 'image/svg+xml'
        });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'graph.svg';
        a.click();
        URL.revokeObjectURL(url);
        //a.parentNode.removeChild(a);
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


    // Render the scene
    function animate() {


        requestAnimationFrame(animate);

        controls.update();

        //console.log(camera.up.x, camera.up.y, camera.up.z, camera.position, camera., XU, YU, ZU)
        if (!wasMouseDown) {

            controls.autoRotate = true; //updateCamera();;
            controls.update();
        } else {
            controls.autoRotate = false; //updateCamera();;
            controls.update();
        }





        renderer.render(scene, camera);
        //     rendererSVG.render(scene, camera);
        //     console.log(rendererSVG.domElement.outerHTML);
    }
    animate();
    return [renderer, scene, onMouseDown, onMove, handleKeyDown, handleKeyUp, STATS, handleKeyDownHide, handleKeyDownHideAnim, exportGLTF, scene1, saveSvg];
}