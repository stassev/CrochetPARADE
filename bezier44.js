var shape_radius=[];
        //const generateButton = document.getElementById('generateButton');
        const generatorDialog = document.getElementById('generatorDialog');
        const numStitchesInput = document.getElementById('numStitches');
        const yAxisLengthDialogInput = document.getElementById('yAxisLengthDialog');
        const xAxisRangeDialogInput = document.getElementById('xAxisRangeDialog');
        const generatorCanvas = document.getElementById('generatorCanvas');
        const thicknessCanvas = document.getElementById('thicknessCanvas');
        const generatorCtx = generatorCanvas.getContext('2d');
        const thicknessCtx = thicknessCanvas.getContext('2d');
        const okayButton = document.getElementById('okayButton');

        const contextMenu = document.getElementById('contextMenu');
        let curveThickness = [];

        function calculateThickness() {
            
            curveThickness = [];

            for (let t = 0; t <= 1000; t ++) {
   
   
                curveThickness.push(5); // Default thickness

            }
        }
        calculateThickness();
var curvePoints=[];
        let yAxisLength = 1.5;
        let xAxisRange = 1.5;
        let points = [];
        let thicknessPoints=[];
        let selectedHandle = null;
        let selectedPoint = null;
        let rightClickPos = null;
        let isShiftPressed = false;
        let isCtrlPressed = false;

        let selectedHandleT = null;
        let selectedPointT = null;
        function updateCanvasSize() {
            generatorCanvas.width = 500*xAxisRange;
            generatorCanvas.height =  500 * yAxisLength;
            thicknessCanvas.width=500*xAxisRange;
thicknessCanvas.height=200;
        }

        function createPoint(x, y) {
            return {
                x: x,
                y: y,
                handleLeft: {x: x - 0.15, y: y},
                handleRight: {x: x + 0.15, y: y}
            };
        }
        function createPointT(x, y) {
            return {
                x: x,
                y: y,
                handleLeft: {x: x - 50, y: y},
                handleRight: {x: x + 50, y: y}
            };
        }
        function createPointM(x, y) {
            return {
                x: x,
                y: y,
                handleLeft: {x: x - 0.4, y: y},
                handleRight: {x: x + 0.4, y: y}
            };
        }

        function createPointIFR(x, y) {
            return {
                x: x,
                y: y,
                handleLeft: {x: x , y: y+0.2},
                handleRight: {x: x, y: y-0}
            };
        }

        function createPointIFL(x, y) {
            return {
                x: x,
                y: y,
                handleLeft: {x: x , y: y-0},
                handleRight: {x: x, y: y+0.2}
            };
        }
        function createPointITR(x, y) {
            return {
                x: x,
                y: y,
                handleLeft: {x: x-50 , y: y},
                handleRight: {x: x, y: y-0}
            };
        }
        function createPointTM(x, y) {
            return {
                x: x,
                y: y,
                handleLeft: {x: x - 50, y: y},
                handleRight: {x: x + 50, y: y}
            };
        }
        function createPointITL(x, y) {
            return {
                x: x,
                y: y,
                handleLeft: {x: x , y: y-0},
                handleRight: {x: x+50, y: y}
            };
        }
        function resetPoints() {
            calculateThickness();
            points = [createPointIFL(0, 0), createPointM(0.5, 0.5), createPointIFR(1, 0)];
            thicknessPoints = [createPointITL(0, 5), createPointTM(500, 5), createPointITR(999, 5)];
            drawCurve();
            drawThicknessCurve();
        }

        function resetThicknessPoints() {
            calculateThickness();
            //points = [createPointIFL(0, 0), createPointM(0.5, 0.5), createPointIFR(1, 0)];
            thicknessPoints = [createPointITL(0, 5), createPointTM(500, 5), createPointITR(999, 5)];
            drawCurve();
            drawThicknessCurve();
        }

        function bernstein(n, i, t) {
            return binomialCoeff(n, i) * Math.pow(t, i) * Math.pow(1 - t, n - i);
        }

        function binomialCoeff(n, k) {
            let coeff = 1;
            for (let i = n - k + 1; i <= n; i++) coeff *= i;
            for (let i = 1; i <= k; i++) coeff /= i;
            return coeff;
        }

        function distance(x1, y1, x2, y2) {
            return Math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2);
        }

        function graphToCanvasT(x, y) {
            return {
                x: (x / 999) * thicknessCanvas.width,
                y: thicknessCanvas.height - ((Math.log(y) - Math.log(2.5)) / (Math.log(10) - Math.log(2.5))) * thicknessCanvas.height
            };
        }

        function canvasToGraphT(canvasX, canvasY) {
            return {
                x: (canvasX / thicknessCanvas.width) * 999,
                y: Math.exp(((thicknessCanvas.height - canvasY) / thicknessCanvas.height) * (Math.log(10) - Math.log(2.5)) + Math.log(2.5))
        
            };
        }
        function canvasToGraph(canvasX, canvasY) {
            return {
                x: (canvasX / generatorCanvas.width) * xAxisRange + (0.5 - xAxisRange / 2),
                y: yAxisLength-(canvasY / generatorCanvas.height) * yAxisLength + ( - yAxisLength / 2), 
                //yAxisLength * (1 - canvasY / generatorCanvas.height)
            };
        }

        function graphToCanvas(x, y) {
            return {
                x: ((x - (0.5 - xAxisRange / 2)) / xAxisRange) * generatorCanvas.width,
                y: generatorCanvas.height -((y - ( - yAxisLength / 2)) / yAxisLength) * generatorCanvas.height,
                //generatorCanvas.height - (y / yAxisLength) * generatorCanvas.height
            };
        }

        function findClosestElement(x, y,points) {
            const threshold = 0.02;
            let closestElement = null;
            let minDistance = Infinity;

            for (const point of points) {
                const pointDist = distance(x, y, point.x, point.y);
                if (pointDist < minDistance && pointDist < threshold) {
                    minDistance = pointDist;
                    closestElement = { type: 'point', element: point };
                }

                const leftHandleDist = distance(x, y, point.handleLeft.x, point.handleLeft.y);
                if (leftHandleDist < minDistance && leftHandleDist < threshold) {
                    minDistance = leftHandleDist;
                    closestElement = { type: 'handle', element: point.handleLeft };
                }

                const rightHandleDist = distance(x, y, point.handleRight.x, point.handleRight.y);
                if (rightHandleDist < minDistance && rightHandleDist < threshold) {
                    minDistance = rightHandleDist;
                    closestElement = { type: 'handle', element: point.handleRight };
                }
            }

            return closestElement;
        }


        function findClosestElementT(x, y,points) {
            const threshold = 0.1;
            let closestElement = null;
            let minDistance = Infinity;

            for (const point of points) {
                const pointDist = distance(x/1000.0, Math.log(y), point.x/1000.0, Math.log(point.y));
                if (pointDist < minDistance && pointDist < threshold) {
                    minDistance = pointDist;
                    closestElement = { type: 'point', element: point };
                }

                const leftHandleDist = distance(x/1000.0, Math.log(y), point.handleLeft.x/1000.0, Math.log(point.handleLeft.y));
                if (leftHandleDist < minDistance && leftHandleDist < threshold) {
                    minDistance = leftHandleDist;
                    closestElement = { type: 'handle', element: point.handleLeft };
                }

                const rightHandleDist = distance(x/1000.0, Math.log(y), point.handleRight.x/1000.0, Math.log(point.handleRight.y));
                if (rightHandleDist < minDistance && rightHandleDist < threshold) {
                    minDistance = rightHandleDist;
                    closestElement = { type: 'handle', element: point.handleRight };
                }
            }

            return closestElement;
        }

        function cubicBezier(p0, p1, p2, p3, t) {
            const mt = 1 - t;
            return mt * mt * mt * p0 +
                   3 * mt * mt * t * p1 +
                   3 * mt * t * t * p2 +
                   t * t * t * p3;
        }

        function calculateThicknessPoints() {
            let thickness = [];
            let i = 0;
            
            for (let t = 0; t <= 1000; t++) {
                // Find the correct interval
                while (i + 1 < thicknessPoints.length && thicknessPoints[i + 1].x <= t) {
                    i++;
                }
                
                if (i + 1 >= thicknessPoints.length) {
                    // We've reached the end, use the last point
                    thickness.push(Math.exp(Math.log(thicknessPoints[i].y)));
                    continue;
                }
                
                const p0 = thicknessPoints[i];
                const p1 = thicknessPoints[i + 1];
                
                // Calculate local t in [0, 1]
                const localT = (t - p0.x) / (p1.x - p0.x);
                
                // Calculate tangents (in log space)
                const m0 = (Math.log(p0.handleRight.y) - Math.log(p0.y)) / (p0.handleRight.x - p0.x);
                const m1 = (Math.log(p1.y) - Math.log(p1.handleLeft.y)) / (p1.x - p1.handleLeft.x);
                
                // Perform cubic Hermite interpolation in log space
                const h00 = 2 * Math.pow(localT, 3) - 3 * Math.pow(localT, 2) + 1;
                const h10 = Math.pow(localT, 3) - 2 * Math.pow(localT, 2) + localT;
                const h01 = -2 * Math.pow(localT, 3) + 3 * Math.pow(localT, 2);
                const h11 = Math.pow(localT, 3) - Math.pow(localT, 2);
                
                const logY = h00 * Math.log(p0.y) + 
                             h10 * m0 * (p1.x - p0.x) + 
                             h01 * Math.log(p1.y) + 
                             h11 * m1 * (p1.x - p0.x);
                
                // Convert back from log space
                thickness.push(Math.exp(logY));
            }
            
            return thickness;
        }

        function calculateCurvePoints() {
            const curvePoints = [];
            //curveThickness = [];
            let n=points.length-1+0.000001;
            for (let t = 0; t <= 1; t += 0.001) {
                const i = Math.floor(t*n);
                const localT = t*n - i;


                const p0 = points[i];
                const p1 = points[i + 1];

                const x = cubicBezier(p0.x, p0.handleRight.x, p1.handleLeft.x, p1.x, localT);
                const y = cubicBezier(p0.y, p0.handleRight.y, p1.handleLeft.y, p1.y, localT);

                curvePoints.push({ x, y });
                //curveThickness.push(5); // Default thickness

            }

            return curvePoints;
        }
        function calculateCurveLengths(curvePoints) {
            const lengths = [0];
            let cumulativeLength = 0;

            for (let i = 1; i < curvePoints.length; i++) {
                const dx = curvePoints[i].x - curvePoints[i-1].x;
                const dy = curvePoints[i].y - curvePoints[i-1].y;
                const segmentLength = Math.sqrt(dx * dx + dy * dy);
                cumulativeLength += segmentLength;
                lengths.push(cumulativeLength);
            }

            return lengths;
        }

        function createInterpolationFunction(curvePoints) {
            const lengths = calculateCurveLengths(curvePoints);
            const totalLength = lengths[lengths.length - 1];

            return function(l) {
                if (l < 0) return curvePoints[0].y*curveThickness[0]/5.0;
                if (l > totalLength) return curvePoints[curvePoints.length - 1].y*curveThickness[curveThickness.length-1];
                let maxl=lengths[lengths.length-1];
                let low = 0;
                let high = lengths.length - 1;
                let index = 0;

                while (low <= high) {
                    const mid = Math.floor((low + high) / 2);
                    if (lengths[mid] < l) {
                        low = mid + 1;
                    } else if (lengths[mid] > l) {
                        high = mid - 1;
                    } else {
                        index = mid;
                        break;
                    }
                    index = low;
                }

                if (index === 0) return curvePoints[0].y;
                const l1 = lengths[index - 1];
                const l2 = lengths[index];
                const y1 = curvePoints[index - 1].y*curveThickness[Math.floor(lengths[index - 1]/maxl*(curveThickness.length-1+0.01))]/5.0;
                const y2 = curvePoints[index].y*curveThickness[Math.floor(lengths[index]/maxl*(curveThickness.length-1+0.01))]/5.0;

                const y = y1 + (y2 - y1) * (l - l1) / (l2 - l1);
                return y;
            };
        }

function drawThicknessGrid() {
    thicknessCtx.strokeStyle = 'gray';
    thicknessCtx.lineWidth = 1;

    // Draw vertical grid lines
    for (let i = 0; i <= 10; i++) {
        const x = (i / 10) * thicknessCanvas.width;
        thicknessCtx.beginPath();
        thicknessCtx.moveTo(x, 0);
        thicknessCtx.lineTo(x, thicknessCanvas.height);
        thicknessCtx.lineWidth=0.25;
        thicknessCtx.stroke();
    }

    // Draw horizontal grid lines
    for (let i = 0; i <= 4; i++) {
        const logYStart = Math.log(2.5);
        const logYEnd = Math.log(10);
        const logYStepSize = (logYEnd - logYStart) / 4;
        const logY = logYStart + i * logYStepSize;
        const y = Math.exp(logY);
        const canvasY = graphToCanvasT(0, y).y;
        thicknessCtx.beginPath();
        thicknessCtx.lineWidth=0.25;
        thicknessCtx.moveTo(0, canvasY);
        thicknessCtx.lineTo(thicknessCanvas.width, canvasY);
        thicknessCtx.stroke();
    }

    // Draw the middle line (for default thickness)
    thicknessCtx.strokeStyle = '#999';
    thicknessCtx.beginPath();
    const middleY = graphToCanvasT(0, 5).y;
    thicknessCtx.moveTo(0, middleY);
    thicknessCtx.lineWidth=3;
    thicknessCtx.lineTo(thicknessCanvas.width, middleY);
    thicknessCtx.stroke();
        // Draw y-axis title
        thicknessCtx.save();
        thicknessCtx.translate(thicknessCanvas.width*0.5, thicknessCanvas.height*0.1);
        //thicknessCtx.rotate(-Math.PI / 2);
        thicknessCtx.textAlign = 'center';
        thicknessCtx.fillStyle = 'rgb(50,50,50)';
        thicknessCtx.font = '14px Arial';
        thicknessCtx.fillText('Adjust between half to twice as many stitches in the round', 0, 0);
        
        thicknessCtx.restore();
}

        function drawGrid() {
    const stepX = 0.1;
    const stepY = 0.1;
    const thickerLineEvery = 5;
    const thickestLineEvery = 10;
    
    const fineLineColor = 'gray';
    const thickLineColor = 'gray';
    const thickestLineColor = '#4CAF50';

    var startX = 0.5 - xAxisRange / 2;
    var startY =  - yAxisLength / 2;
    startX=Math.floor(startX/stepX)*stepX;
    startY=Math.floor(startY/stepY)*stepY;
    for (let i = startX-stepX; i <= stepX+startX + xAxisRange; i += stepX) {
        const x = graphToCanvas(i, 0).x;
        if (x < 0 || x > generatorCanvas.width) continue;

        generatorCtx.beginPath();
        generatorCtx.moveTo(x, 0);
        generatorCtx.lineTo(x, generatorCanvas.height);

        const lineIndex = Math.abs(Math.round(i / stepX));
        if (lineIndex % thickestLineEvery === 0) {
            generatorCtx.strokeStyle = thickestLineColor;
            generatorCtx.lineWidth = 3;
        } else if (lineIndex % thickerLineEvery === 0) {
            generatorCtx.strokeStyle = thickLineColor;
            generatorCtx.lineWidth = 0.75;
        } else {
            generatorCtx.strokeStyle = fineLineColor;
            generatorCtx.lineWidth = 0.25;
        }
        generatorCtx.stroke();
    }

    for (let j = startY-stepY; j <= stepY+startY + yAxisLength; j += stepY) {
        const y = graphToCanvas(0, j).y;
        if (y < 0 || y > generatorCanvas.height) continue;

        generatorCtx.beginPath();
        generatorCtx.moveTo(0, y);
        generatorCtx.lineTo(generatorCanvas.width, y);

        const lineIndex = Math.abs(Math.round(j / stepY));
        if (lineIndex % thickestLineEvery === 0) {
            generatorCtx.strokeStyle = thickestLineColor;
            generatorCtx.lineWidth = 3;
        } else if (lineIndex % thickerLineEvery === 0) {
            generatorCtx.strokeStyle = thickLineColor;
            generatorCtx.lineWidth = 0.75;
        } else {
            generatorCtx.strokeStyle = fineLineColor;
            generatorCtx.lineWidth = 0.25;
        }
        generatorCtx.stroke();
    }
}


function drawThicknessCurve() {
    thicknessCtx.clearRect(0, 0, thicknessCanvas.width, thicknessCanvas.height);

    drawThicknessGrid();

    thicknessCtx.beginPath();

    if (thicknessPoints.length === 0) return;

    //thicknessPoints = calculateThickness();
    //const lengths = calculateCurveLengths(thicknessPoints);
    thicknessCtx.beginPath();
    curveThickness = calculateThicknessPoints();
//console.log(curveThickness)

    thicknessCtx.beginPath();
    if (curveThickness.length > 0) {
        const p0 = graphToCanvasT(0, curveThickness[0]);
        thicknessCtx.moveTo(p0.x, p0.y);
        for (let i = 1; i < curveThickness.length; i++) {
            let yy = curveThickness[i];
            const p = graphToCanvasT(i, yy);
            thicknessCtx.lineTo(p.x, p.y);
            thicknessCtx.lineWidth = 5;
            thicknessCtx.strokeStyle = 'blue';
            thicknessCtx.stroke();
            thicknessCtx.beginPath();
            thicknessCtx.moveTo(p.x, p.y);
        }
    }

  // if (thicknessPoints.length > 0) {
  //     const p0= graphToCanvasT(thicknessPoints[0].x, thicknessPoints[0].y);
  //      thicknessCtx.moveTo(p0.x,p0.y);
  //      for (let i = 1; i < thicknessPoints.length; i++) {
  //          const p= graphToCanvasT(thicknessPoints[i].x, thicknessPoints[i].y);
  //          thicknessCtx.lineTo(p.x,p.y);
  //      }
  //  }
  // thicknessCtx.strokeStyle = 'blue';
  // thicknessCtx.lineWidth = 5;  // Make the line thicker
  // thicknessCtx.stroke();

    thicknessPoints.forEach((point, index) => {
        const canvasPoint = graphToCanvasT(point.x, point.y);
        const canvasHandleLeft = graphToCanvasT(point.handleLeft.x, point.handleLeft.y);
        const canvasHandleRight = graphToCanvasT(point.handleRight.x, point.handleRight.y);
        drawHandle(canvasPoint.x, canvasPoint.y, canvasHandleLeft.x, canvasHandleLeft.y,thicknessCtx);
        drawHandle(canvasPoint.x, canvasPoint.y, canvasHandleRight.x, canvasHandleRight.y,thicknessCtx);
        drawPoint(canvasPoint.x, canvasPoint.y, index === 0 || index === thicknessPoints.length - 1 ? '#f44336' : 'black',thicknessCtx);
    });
    drawCurve();
}

        function drawCurve() {
            generatorCtx.clearRect(0, 0, generatorCanvas.width, generatorCanvas.height);

            drawGrid();

            generatorCtx.beginPath();

            if (points.length === 0) return;

            curvePoints = calculateCurvePoints();
            const lengths = calculateCurveLengths(curvePoints);
            const maxl=lengths[lengths.length-1];
            generatorCtx.beginPath();
            if (curvePoints.length > 0) {
                const p0 = graphToCanvas(curvePoints[0].x, curvePoints[0].y);
                generatorCtx.moveTo(p0.x, p0.y);
                for (let i = 1; i < curvePoints.length; i++) {
                    let yy = curvePoints[i].y;
                    if (yy < 0) yy = 0;
                    const p = graphToCanvas(curvePoints[i].x, yy);
                    generatorCtx.lineTo(p.x, p.y);
                    generatorCtx.lineWidth = (curveThickness[Math.floor(lengths[i]/maxl*(curvePoints.length-1+0.01))]/5)**3*5;
                    generatorCtx.strokeStyle = 'blue';
                    generatorCtx.stroke();
                    generatorCtx.beginPath();
                    generatorCtx.moveTo(p.x, p.y);
                }
            }
            if (curvePoints.length > 0) {
                const p0= graphToCanvas(curvePoints[0].x, -curvePoints[0].y);
                 generatorCtx.moveTo(p0.x,p0.y);
                 for (let i = 1; i < curvePoints.length; i++) {
                    let yy = curvePoints[i].y;
                    if (yy < 0) yy = 0;
                    const p = graphToCanvas(curvePoints[i].x, -yy);
                    generatorCtx.lineTo(p.x, p.y);
                    generatorCtx.lineWidth = (curveThickness[Math.floor(lengths[i]/maxl*(curvePoints.length-1+0.01))]/5)**3*5;
                    generatorCtx.strokeStyle = 'blue';
                    generatorCtx.stroke();
                    generatorCtx.beginPath();
                    generatorCtx.moveTo(p.x, p.y);
                 }
             }
            generatorCtx.strokeStyle = 'blue';
            generatorCtx.lineWidth = 5;  // Make the line thicker
            generatorCtx.stroke();

            points.forEach((point, index) => {
                const canvasPoint = graphToCanvas(point.x, point.y);
                const canvasHandleLeft = graphToCanvas(point.handleLeft.x, point.handleLeft.y);
                const canvasHandleRight = graphToCanvas(point.handleRight.x, point.handleRight.y);
                drawHandle(canvasPoint.x, canvasPoint.y, canvasHandleLeft.x, canvasHandleLeft.y,generatorCtx);
                drawHandle(canvasPoint.x, canvasPoint.y, canvasHandleRight.x, canvasHandleRight.y,generatorCtx);

                drawPoint(canvasPoint.x, canvasPoint.y, index === 0 || index === points.length - 1 ? 'red' : 'black',generatorCtx);
            });
        }
        function findClosestCurvePoint(x, y) {
            const maxDistance = 0.05; // Maximum distance to consider
            let closestIndex = -1;
            let minDistance = Infinity;
        
            for (let i = 0; i < curvePoints.length; i++) {
                const d = distance(x, y, curvePoints[i].x, curvePoints[i].y);
                if (d < minDistance && d < maxDistance) {
                    minDistance = d;
                    closestIndex = i;
                }
            }
        
            return closestIndex;
        }
        var closestIndex=-1;
        generatorCanvas.addEventListener('mousemove', function(e) {
            const rect = generatorCanvas.getBoundingClientRect();
            const graphPos = canvasToGraph(e.clientX - rect.left, e.clientY - rect.top);
            closestIndex = findClosestCurvePoint(graphPos.x, graphPos.y);
        });
        
        function drawPoint(x, y, color,ctx) {
            ctx.fillStyle = color;
            ctx.beginPath();
            ctx.arc(x, y, 7, 0, Math.PI * 2);
            ctx.fill();
        }

        function drawHandle(x1, y1, x2, y2,ctx) {
            ctx.beginPath();
            ctx.moveTo(x1, y1);
            ctx.lineTo(x2, y2);
            ctx.strokeStyle = '#fbce1a';
       ctx.stroke();
            ctx.fillStyle = 'magenta';
            ctx.beginPath();
            ctx.arc(x2, y2, 5, 0, Math.PI * 2);
            ctx.fill();
        }

        function updateYAxisLength(newYAxisLength) {
            yAxisLength = newYAxisLength;
            if (!(isNaN(yAxisLength) || yAxisLength <= 0)) {
                
            updateCanvasSize();
            drawCurve();
            drawThicknessCurve();
            }
        }

        function updateXAxisRange(newXAxisRange) {
            xAxisRange = newXAxisRange;
            if (!(isNaN(xAxisRange) || xAxisRange <= 0) ){
                
            
            updateCanvasSize();
            drawThicknessCurve();
            drawCurve();
            }
        }

        
        thicknessCanvas.addEventListener('mousedown', function(e) {
            const rect = thicknessCanvas.getBoundingClientRect();
            const graphPos = canvasToGraphT(e.clientX - rect.left, e.clientY - rect.top);
            if (e.button === 0) {
                const closestElement = findClosestElementT(graphPos.x, graphPos.y,thicknessPoints);
                if (closestElement) {
                    if (closestElement.type === 'point') {
                        selectedPointT = closestElement.element;
                    } else if (closestElement.type === 'handle') {
                        selectedHandleT = closestElement.element;
                    }
                    drawThicknessCurve();
                }
            }
        });

        generatorCanvas.addEventListener('mousedown', function(e) {
            const rect = generatorCanvas.getBoundingClientRect();
            const graphPos = canvasToGraph(e.clientX - rect.left, e.clientY - rect.top);
            if (e.button === 0) {
                const closestElement = findClosestElement(graphPos.x, graphPos.y,points);
                if (closestElement) {
                    if (closestElement.type === 'point') {
                        selectedPoint = closestElement.element;
                    } else if (closestElement.type === 'handle') {
                        selectedHandle = closestElement.element;
                    }
                    //drawCurve();
                }
            }
        });

function onMove(selectedPoint,selectedHandle,generatorCanvas,canvasToGraph,points,drawCurve,e,thicknessQ){  
    if (!selectedPoint && !selectedHandle) return;

    const rect = generatorCanvas.getBoundingClientRect();
    const graphPos = canvasToGraph(e.clientX - rect.left, e.clientY - rect.top);

    if (selectedHandle) {
        const parentPoint = points.find(p => p.handleLeft === selectedHandle || p.handleRight === selectedHandle);
    //    if (parentPoint) {  // Make sure parentPoint is found
            const isLeftHandle = parentPoint.handleLeft === selectedHandle;

            if (isShiftPressed) {
                const dx = graphPos.x - parentPoint.x;
                const dy = graphPos.y - parentPoint.y;
                const angle = Math.atan2(dy, dx);
                const handleDistance = distance(parentPoint.x, parentPoint.y, graphPos.x, graphPos.y);

            const leftLength = distance(parentPoint.x, parentPoint.y, parentPoint.handleLeft.x, parentPoint.handleLeft.y);
            const rightLength = distance(parentPoint.x, parentPoint.y, parentPoint.handleRight.x, parentPoint.handleRight.y);

            if (isLeftHandle && (parentPoint !== points[0])) {
                const newLeftLength = distance(parentPoint.x, parentPoint.y, graphPos.x, graphPos.y);

                parentPoint.handleLeft.x = parentPoint.x + newLeftLength * Math.cos(angle);
                parentPoint.handleLeft.y = parentPoint.y + newLeftLength * Math.sin(angle);
                
                if (parentPoint !== points[points.length - 1]){
                parentPoint.handleRight.x = parentPoint.x - rightLength * Math.cos(angle);
                parentPoint.handleRight.y = parentPoint.y - rightLength * Math.sin(angle);
                }
            } else if ((!isLeftHandle) && parentPoint !== points[points.length - 1]) {
                const newRightLength = distance(parentPoint.x, parentPoint.y, graphPos.x, graphPos.y);
                
                parentPoint.handleRight.x = parentPoint.x + newRightLength * Math.cos(angle);
                parentPoint.handleRight.y = parentPoint.y + newRightLength * Math.sin(angle);
                
                if(parentPoint !== points[0]){
                parentPoint.handleLeft.x = parentPoint.x - leftLength * Math.cos(angle);
                parentPoint.handleLeft.y = parentPoint.y - leftLength * Math.sin(angle);
            }
            }
        } else if (isCtrlPressed) {
            const dx = graphPos.x - parentPoint.x;
            const dy = graphPos.y - parentPoint.y;
            const angle = Math.atan2(dy, dx);
            const distance = Math.sqrt(dx * dx + dy * dy);
            if (isLeftHandle && (parentPoint !== points[0])) {
                
                parentPoint.handleLeft.x = parentPoint.x + distance * Math.cos(angle);
                parentPoint.handleLeft.y = parentPoint.y + distance * Math.sin(angle);
                
                if (parentPoint !== points[points.length - 1]){
                parentPoint.handleRight.x = parentPoint.x - distance * Math.cos(angle);
                parentPoint.handleRight.y = parentPoint.y - distance * Math.sin(angle);
                }
            } else if ((!isLeftHandle) && parentPoint !== points[points.length - 1]) {
                
                parentPoint.handleRight.x = parentPoint.x + distance * Math.cos(angle);
                parentPoint.handleRight.y = parentPoint.y + distance * Math.sin(angle);
                
                if(parentPoint !== points[0]){
                parentPoint.handleLeft.x = parentPoint.x - distance * Math.cos(angle);
                parentPoint.handleLeft.y = parentPoint.y - distance * Math.sin(angle);
            }
            }



            } else {
                if (((parentPoint !== points[0])&&(parentPoint !== points[points.length - 1]))|| ((!isLeftHandle) && (parentPoint == points[0])) || ((isLeftHandle)&& (parentPoint == points[points.length - 1]) ))
                selectedHandle.x = graphPos.x;
                selectedHandle.y = graphPos.y;
            }
    } else if (selectedPoint){// && selectedPoint !== points[0] && selectedPoint !== points[points.length - 1]) {
        const dx = graphPos.x - selectedPoint.x;
        const dy = Math.max(graphPos.y,0) - selectedPoint.y;
        if ((!thicknessQ) || ( selectedPoint !== points[0] && selectedPoint !== points[points.length - 1])){
            selectedPoint.x = graphPos.x;
            selectedPoint.handleLeft.x += dx;
            selectedPoint.handleRight.x += dx;
        }
       
        selectedPoint.y = Math.max(graphPos.y,0);
        selectedPoint.handleLeft.y += dy;
        selectedPoint.handleRight.y += dy;
if (thicknessQ){
        const firstPoint = points.shift(); // Remove and store the first point
        const lastPoint = points.pop();   // Remove and store the last point
        
        // Push the new point
      
        points.sort((a, b) => a.x - b.x);
        
        // Add back the first and last points
        if (firstPoint) points.unshift(firstPoint); // Add the first point back to the beginning
        if (lastPoint) points.push(lastPoint);      // Add the last point back to the end
}

    }

    drawCurve();
}
thicknessCanvas.addEventListener('mousemove', function(e) {
    onMove(selectedPointT,selectedHandleT,thicknessCanvas,canvasToGraphT,thicknessPoints,drawThicknessCurve,e,true);
});

        generatorCanvas.addEventListener('mousemove', function(e) {
            onMove(selectedPoint,selectedHandle,generatorCanvas,canvasToGraph,points,drawCurve,e,false);
        });

        generatorCanvas.addEventListener('mouseup', function() {
            selectedPoint = null;
            selectedHandle = null;
        });


        thicknessCanvas.addEventListener('mouseup', function() {
            selectedPointT = null;
            selectedHandleT = null;
        });

        generatorCanvas.addEventListener('contextmenu', function(e) {
            e.preventDefault();
            const rect = generatorCanvas.getBoundingClientRect();
            rightClickPos = canvasToGraph(e.clientX - rect.left, e.clientY - rect.top);
            rightClickPos['thicknessQ']=false;
            contextMenu.style.display = 'block';
            contextMenu.style.left = e.clientX + 'px';
            contextMenu.style.top = e.clientY + 'px';
        });
        thicknessCanvas.addEventListener('contextmenu', function(e) {
            e.preventDefault();
            const rect = thicknessCanvas.getBoundingClientRect();
            rightClickPos = canvasToGraphT(e.clientX - rect.left, e.clientY - rect.top);       
                rightClickPos['thicknessQ']=true;
            contextMenu.style.display = 'block';
            contextMenu.style.left = e.clientX + 'px';
            contextMenu.style.top = e.clientY + 'px';
        });
//        let touchStartTime;
//let touchCount = 0;
//generatorCanvas.addEventListener('touchstart', function(e) {
//    console.log("Touch start on canvas", e.touches.length);
//    touchStartTime = Date.now();
//    touchCount = e.touches.length;
//}, { passive: true });
//
//generatorCanvas.addEventListener('touchend', function(e) {
//    console.log("Touch end on canvas", touchCount);
//    if (touchCount === 2 && (Date.now() - touchStartTime) < 100) {
//        e.preventDefault();
//        const rect = generatorCanvas.getBoundingClientRect();
//        const touch = e.changedTouches[0];
//        rightClickPos = canvasToGraph(touch.clientX - rect.left, touch.clientY - rect.top);
//        contextMenu.style.display = 'block';
//        contextMenu.style.left = touch.clientX + 'px';
//        contextMenu.style.top = touch.clientY + 'px';
//    }
//    touchCount = 0;
//}, { passive: false });

document.addEventListener('click', function(e) {
            //if (e.target.id !== 'addPoint' && e.target.id !== 'deletePoint') {
                contextMenu.style.display = 'none';
            //}
        });

        document.getElementById('addPoint').addEventListener('click', function() {
            if (rightClickPos) {
                let ps=points;
                if (rightClickPos.thicknessQ)
                        ps=thicknessPoints;
                const firstPoint = ps.shift(); // Remove and store the first point
const lastPoint = ps.pop();   // Remove and store the last point

// Push the new point
if (rightClickPos.thicknessQ)
ps.push(createPointT(rightClickPos.x, rightClickPos.y));
else
ps.push(createPoint(rightClickPos.x, rightClickPos.y));
// Sort the remaining points by their x-coordinate
ps.sort((a, b) => a.x - b.x);

// Add back the first and last points
if (firstPoint) ps.unshift(firstPoint); // Add the first point back to the beginning
if (lastPoint) ps.push(lastPoint);      // Add the last point back to the end
                if (rightClickPos.thicknessQ)
drawThicknessCurve();
                    else 
                    drawCurve(); 
            }
        });

        document.getElementById('deletePoint').addEventListener('click', function() {
            if (rightClickPos) {
                    if (!rightClickPos.thicknessQ){
                        const closestElement = findClosestElement(rightClickPos.x, rightClickPos.y,points);
                        if (closestElement && closestElement.type === 'point') {
                            points = points.filter(p => p !== closestElement.element);
                            drawCurve();
                        }
                    }else{ const closestElement = findClosestElementT(rightClickPos.x, rightClickPos.y,thicknessPoints);
                        if (closestElement && closestElement.type === 'point') {
                            thicknessPoints = thicknessPoints.filter(p => (p !== closestElement.element || p===thicknessPoints[0] || p===thicknessPoints[thicknessPoints.length-1]));
                            drawThicknessCurve();
                        }}

               
            }
        });

        document.addEventListener('keydown', function(e) {
            if (e.key === 'Shift') {
                isShiftPressed = true;
            } else if (e.key === 'Control') {
                isCtrlPressed = true;
            }
        });

        document.addEventListener('keyup', function(e) {
            if (e.key === 'Shift') {
                isShiftPressed = false;
            } else if (e.key === 'Control') {
                isCtrlPressed = false;
            }
        });

        yAxisLengthDialogInput.addEventListener('input', function() {
            updateYAxisLength(parseFloat(this.value));
        });

        xAxisRangeDialogInput.addEventListener('input', function() {
            updateXAxisRange(parseFloat(this.value));
        });


        function generate_shape(scatter=true) {
            // Helper functions
            function ceiling(n) {
              return Math.ceil(n);
            }
          
            function floor(n) {
              return Math.floor(n);
            }
          
            function range(start, end, step = 1) {
              return Array.from({ length: (end - start) / step + 1 }, (_, i) => start + i * step);
            }
          
           function balancedAlternatingPartition(n, m) {
            const base = Math.floor(n / m);
            const remainder = n % m;
            const larger = Array(remainder).fill(base + 1);
            const smaller = Array(m - remainder).fill(base);
            const result = Array(m).fill(0);
          
            let largerIndex = 0;
            let smallerIndex = 0;
          
            for (let i = 0; i < m; i++) {
              if (i % 2 === 0) {
                result[i] = largerIndex < larger.length ? larger[largerIndex++] : smaller[smallerIndex++];
              } else {
                result[i] = smallerIndex < smaller.length ? smaller[smallerIndex++] : larger[largerIndex++];
              }
            }
          
            return result;
          }
          
          
            function replaceSequence(list) {
               
            const result = [];
            let i = 0;
            while (i < list.length) {
                let count = 1;
                while (i + count < list.length && list[i + count] === 0) {
                  count++;
                }
                if (count > 1) {
                  result.push(`sc${count}tog`);
                  i += count;
                } else {
                  result.push(list[i]);
                  i++;
                }
            }
            return result;
          }
          
          
            function distributeEvenly(list) {
              const sc = list.filter(item => item === "sc");
              const nonSc = list.filter(item => item !== "sc");
              const scCount = sc.length;
              const nonScCount = nonSc.length;
          
              if (nonScCount === 0) return list;
              if (scCount === 0) return list;
          
              const groupSizes = Array.from({ length: nonScCount }, (_, i) => Math.floor((scCount + i) / nonScCount));
              const result = [];
          
              for (let i = 0; i < nonScCount; i++) {
                result.push(nonSc[i]);
                result.push(...Array(groupSizes[i]).fill("sc"));
              }
          
              //if (list[0] === "sc" && result[0] !== "sc") result.unshift("sc");
              //if (list[list.length - 1] === "sc" && result[result.length - 1] !== "sc") result.push("sc");
          
              const resultScCount = result.filter(item => item === "sc").length;
              const resultNonScCount = result.filter(item => item !== "sc").length;
          
              if (resultScCount !== scCount || resultNonScCount !== nonScCount) {
                throw new Error("Mismatch in item counts between original list and result");
              }
              return result;
            }
          
            function longestConsecutiveSC(arr) {
              //const arr = str.split(',');
              let maxCount = 0;
              let currentCount = 0;
            
              for (let item of arr) {
                if (item.trim() === 'sc') {
                  currentCount++;
                  maxCount = Math.max(maxCount, currentCount);
                } else {
                  currentCount = 0;
                }
              }
            
              return maxCount;
            }
            
          let Si = 0;
          
          function cyclicPermuteBySC(list) {
            // Split the list into groups, keeping only the 'sc' groups
            //const a = list.join(',').split(',sc,').map(group => group.split(','))
            //              .filter(group => group[0] === 'sc' || group[group.length - 1] === 'sc');
            
            //if (a.length === 0) return list;
            
            Si++;
            let count = Math.max(Math.ceil(list.length / 18),(list.length > 18*4 ?Math.ceil(longestConsecutiveSC(list)/6):0)) * (Si % 4)  + (list.length > 18*4 ? Si : 0);
            count=count % list.length;
            // RotateLeft in JavaScript
            return [...list.slice(count), ...list.slice(0, count)];
          }
          
          
            function listToString(nestedList) {
              return nestedList.map(sublist => sublist.join(',')).join('\n');
            }
          
            function rewritePattern(input) {
              const lines = input.split('\n');
          
              function handleScInc(tokens) {
                const result = [];
                let i = 0;
                while (i < tokens.length) {
                  if (tokens[i] === "sc" && i < tokens.length - 1 && tokens[i + 1].startsWith("sc@")) {
                    let count = 1;
                    while (i + count < tokens.length && tokens[i + count].startsWith("sc@")) {
                      count++;
                    }
                    result.push(`sc${count}inc`);
                    i += count;
                  } else {
                    result.push(tokens[i]);
                    i++;
                  }
                }
                return result;
              }
          
              function groupRepeats(tokens) {
                const result = [];
                let i = 0;
                while (i < tokens.length) {
                  let count = 1;
                  while (i + count < tokens.length && tokens[i + count] === tokens[i]) {
                    count++;
                  }
                  result.push(count > 1 ? `${count}*${tokens[i]}` : tokens[i]);
                  i += count;
                }
                return result;
              }
          
              function processLine(line) {
                const tokens = line.split(',');
                const intermediate = handleScInc(tokens);
                return groupRepeats(intermediate).join(',');
              }
          
              return lines.map(processLine).join('\n');
            }
          
            function combineRepeatedSeries(input) {
              const tokens = input.split(',');
              const result = [];
              let i = 0;
          
              while (i < tokens.length - 1) {
                const pattern = [tokens[i], tokens[i + 1]];
                let count = 0;
                while (i + count * 2+1 < tokens.length && 
                       tokens.slice(i + count * 2, i + count * 2 + 2).join(',') === pattern.join(',')) {
                  count++;
                }
                if (count > 1) {
                  result.push(`${count}*[${pattern.join(',')}]`);
                  i += count * 2;
                } else {
                  result.push(tokens[i]);
                  i++;
                }
              }
          
              if (i < tokens.length) {
                result.push(tokens[i]);
              }
          
              return result.join(',');
            }
          
            // Main function logic
           console.log(shape_radius);
            //const lat = range(0, Nlat).map(i => (i / Nlat) * Math.PI);
            const icirc = shape_radius.map(l => Math.max(1,floor(l*2*Math.PI+1.e-7)));
            
            const tab = [];
            for (let i = 0; i < icirc.length - 1; i++) {
              const z = balancedAlternatingPartition(icirc[i + 1], icirc[i]);
              if (z.reduce((a, b) => a + b, 0) - icirc[i + 1] !== 0) {
                console.log("Error");
              }
              tab.push(z);
            }
          
            const in_ = tab.map(row => 
              row.map(i => i > 1 ? `sc${i}inc` : (i < 1 ? 0:"sc"))
            );
            //in_[0][0] += "@R";
            //console.log(in_)
            const out0 = in_.map(replaceSequence);
            const out = out0.map(distributeEvenly);
            let outA=out;
            if (scatter)
               outA = out.map(cyclicPermuteBySC);
            var  out2 =listToString(outA);
            if (icirc[0]==1)    
                out2= "ring\n" + out2;
            else 
                out2=Array(icirc[0]).fill('ch').join(',')+'\n'+out2;
            console.log(out2)
            const out3 = rewritePattern(out2);
            const out4 = combineRepeatedSeries(out3);
          
            return out4.replace(/\*s/g, "s");
          }
          

          document.addEventListener('DOMContentLoaded', function() {
            const thicknessB = document.getElementById('thicknessB');
            const thicknessContainer = document.getElementById('thicknessContainer');
            const resetThicknessBtn = document.getElementById('resetThicknessBtn');
          
            thicknessB.addEventListener('change', function() {
              thicknessContainer.style.display = this.checked ? 'block' : 'none';
            });
          
            resetThicknessBtn.addEventListener('click', function() {
              // This function will be defined later
              
              resetThicknessPoints();
            });

  // Call drawThicknessGrid when the canvas is visible
  const observer = new MutationObserver(function(mutations) {
    mutations.forEach(function(mutation) {
      if (mutation.type === 'attributes' && mutation.attributeName === 'style') {
        if (thicknessContainer.style.display !== 'none') {
          drawThicknessGrid();
          drawThicknessCurve();
        }
      }
    });
  });

  observer.observe(thicknessContainer, { attributes: true });
});
