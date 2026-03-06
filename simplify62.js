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

function processLabels(labels) {

    const pattern = /^(@|\.)(\d*)([a-zA-Z_]+[a-zA-Z_0-9]*)\[((\d*)(,\d+)*)\](\[\d+\])?([!\+~\^0-9]*)$/;

    // Step 1: Filter labels that match the pattern
    const labelsToWorkWith = labels
        .map(([_, label]) => label) // Extract second elements
        .filter(label => pattern.test(label)); // Match labels with regex

    // Step 2: Function to split a label into groups
    function splitLabel(label) {
        const match = label.match(pattern);
        if (!match) return null;

        const group1 = match[1]; // (@|\.)
        const group2 = match[2] ? parseInt(match[2], 10) : 0; // (\d*) or default to 0
        const group3 = match[3]; // ([a-zA-Z_]+[a-zA-Z_0-9]*)

        // Extract numbers inside the first square brackets
        const group4Match = match[4];
        const group4 = group4Match ? group4Match.split(",").map(Number) : [];

        const lastGroupPresent = !!match[7]; // Check if the last group (\[\d+\])* is present
        const group5 = lastGroupPresent ? parseInt(match[7].slice(1, -1), 10) : -1; // Extract number from last group or -1

        const trailingChar = match[8] || ''; // Extract trailing character or default to ''

        return [group1, group2, group3, group4, group5, trailingChar];
    }

    // Step 3: Function to reconstitute a label from groups
    function reconstituteLabel(groups) {
        const group1 = groups[0];
        const group2 = groups[1] !== 0 ? String(groups[1]) : "";
        const group3 = groups[2];
        const group4 = '[' + groups[3].join(",") + ']';
        const group5 = groups[4] !== -1 ? `[${groups[4]}]` : ""; // Add group5 only if it's not -1
        const trailingChar = groups[5] || ''; // Add trailing character

        return `${group1}${group2}${group3}${group4}${group5}${trailingChar}`;
    }

    function reconstituteLabelfromSymbolic(groups) {
        const group1 = groups[0][0];
        const group2 = groups[0][1] !== 0 ? String(groups[0][1]) : "";
        const group3 = groups[0][2];
        const group4 = '[' + groups[1].slice(0, -1).join(",") + ']';
        const group5 = groups[1].slice(-1)[0] !== -1 ? `[${groups[1].slice(-1)[0]}]` : ""; // Add group5 only if it's not -1
        const trailingChar = groups[0][3] || ''; // Add trailing character

        return `${group1}${group2}${group3}${group4}${group5}${trailingChar}`;
    }

    // Example usage:
    const splitLabels = labelsToWorkWith.map(label => splitLabel(label));
    const reconstructedLabels = splitLabels.map(groups => reconstituteLabel(groups));

    // Output results
    console.log("Labels to work with:", labelsToWorkWith);
    console.log("Split labels:", splitLabels);
    input = splitLabels.map(label => [
        [label[0], label[1], label[2], label[5]],
        [...label[3], label[4]]
    ]);
    console.log(
        input);
    console.log("Reconstructed labels:", reconstructedLabels);
    let x = symbolicIndices(input, 4);
    if (x !== null)
        return [labelsToWorkWith, x.map(l => reconstituteLabelfromSymbolic(l))];
    else
        return null;
}

function symbolicIndices(input, MaxIndexJump = 1) {


    function generateSymbolicIndices(input) {
        // 1. Group by input[i][0]
        const grouped = new Map();
        input.forEach(item => {
            const key = item[0];
            if (!grouped.has(key)) {
                grouped.set(key, []);
            }
            grouped.get(key).push(item[1]);
        });

        // Helper function to generate variable names
        function generateVariableName(index) {
            let base = "";
            let i = index;

            do {
                const remainder = i % 52; // 26 lowercase + 26 uppercase
                base = String.fromCharCode(remainder < 26 ? 97 + remainder : 65 + (remainder - 26)) + base;
                i = Math.floor(i / 52) - 1;
            } while (i >= 0);

            return "var" + base;
        }
        // 2. & 3. Create Labels and Check Differences
        const labelCounters = {}; // Store label counters for each subgroup
        const symbolicGroups = new Map();
        const labelNumber = {};

        for (const [key, values] of grouped) {
            symbolicGroups.set(key, []);
            const groupSymbolic = [];
            if (!(key in labelNumber))
                labelNumber[key] = 1;
            else
                labelNumber[key]++;
            for (const value of values) {
                const numericSubarray = value || [];
                const symbolicSubarray = [];

                for (let k = 0; k < numericSubarray.length; k++) {
                    const labelKey = `${key}_${k}`; // Unique label for each index
                    if (numericSubarray[k] === -1) {
                        symbolicSubarray.push(-1);
                        continue;
                    }

                    if (labelCounters[labelKey] === undefined) {
                        let variableName = generateVariableName(Object.keys(labelCounters).length);
                        labelCounters[labelKey] = {
                            label: variableName,
                            count: numericSubarray[k]
                        }; // start from 'a' // start from 'a'
                        symbolicSubarray.push('$' + `${labelCounters[labelKey].label}=${numericSubarray[k]}` + '$' + labelCounters[labelKey].label);
                    } else {
                        const diff = numericSubarray[k] - labelCounters[labelKey].count;

                        if (Math.abs(diff) <= MaxIndexJump) {
                            if (Math.abs(diff) <= 1) {
                                const prefix = diff === 1 ? '++' : diff === -1 ? '--' : '';
                                symbolicSubarray.push(`${prefix}${labelCounters[labelKey].label}`);
                                labelCounters[labelKey].count = numericSubarray[k];
                            } else {
                                let multiIncrement = '';
                                let numRepeats = Math.abs(diff) - 1
                                let symbol = diff > 0 ? '++' : '--'
                                for (let i = 0; i < numRepeats; ++i) {
                                    multiIncrement += symbol + labelCounters[labelKey].label + ',';
                                }
                                multiIncrement = multiIncrement.slice(0, -1)
                                symbolicSubarray.push('$' + multiIncrement + '$' + (diff > 0 ? '++' : '--') + labelCounters[labelKey].label);
                                labelCounters[labelKey].count = numericSubarray[k];
                            }

                        } else {
                            labelCounters[labelKey].count = numericSubarray[k];
                            symbolicSubarray.push('$' + `${labelCounters[labelKey].label}=${numericSubarray[k]}` + '$' + labelCounters[labelKey].label); // reset label
                        }
                    }
                }
                groupSymbolic.push(symbolicSubarray);

            }
            symbolicGroups.set(key, groupSymbolic);
        }
        // 4. Re-insert Label-Type Indices
        const result = [];
        input.forEach(item => {
            const key = item[0];
            //console.log(key, ' ', grouped.get(key).length, ' ', grouped.get(key))
            if (symbolicGroups.has(key) && (labelNumber[key] >= 3)) {
                const symbolicGroup = symbolicGroups.get(key);
                if (symbolicGroup.length > 0) {
                    result.push([key, symbolicGroup.shift()]); // Use shift() to maintain order within each group
                }
            } else if (symbolicGroups.has(key))
                result.push([key, item[1]]);
        });


        return result;
    }
    // 5. Function to Evaluate Label Expressions
    function evaluateLabelExpressions(arr) {
        const labelValues = {};

        return arr.map(item => {
            const label = item[0];
            const symbolicIndices = item[1];
            const evaluatedIndices = symbolicIndices.map(index => {
                if (typeof index === 'number') {
                    return index; // Keep -1 as is
                }


                if (index.includes("=")) {
                    let [variable, initialValue] = index.split("=");
                    variable = variable.slice(1);
                    labelValues[variable] = parseInt(initialValue);
                    return labelValues[variable];
                }
                if (index.startsWith("++")) {
                    const variable = index.slice(2);
                    if (labelValues[variable] === undefined) {
                        console.log("Found undefined value ", variable)
                    }
                    labelValues[variable]++;
                    return labelValues[variable];
                } else if (index.startsWith("--")) {
                    const variable = index.slice(2);
                    if (labelValues[variable] === undefined) {
                        console.log("Found undefined value ", variable)
                    }
                    labelValues[variable]--;
                    return labelValues[variable];
                } else if (index.startsWith("$")) { //check to see if it ends with the variable name
                    let variable = index.split('$')[2].slice(2); //extract variable at the end
                    if (labelValues[variable] === undefined) {
                        console.log("Found undefined value ", variable)
                    }
                    let diff = ((index.match(/\+/g) || []).length) - ((index.match(/-/g) || []).length);
                    labelValues[variable] += diff / 2;
                    result = labelValues[variable];


                    return labelValues[variable]
                } else {
                    let variable = index;
                    if (labelValues[variable] === undefined) {
                        console.log("Found undefined value ", variable)
                    }


                    return labelValues[variable];
                }



            });
            return [label, evaluatedIndices];
        });
    }

    // 6. Function to Extract Original Labels with Subarrays
    //function extractOriginalLabels(data) {
    //    return data.map(item => [item[0], item[1]]);
    // }


    const symbolicResult = generateSymbolicIndices(input);
    const evaluatedResult = evaluateLabelExpressions(symbolicResult);
    // const originalLabelsExtracted = extractOriginalLabels(input);

    // Output Results
    console.log("Symbolic Result:", JSON.stringify(symbolicResult));
    console.log("Evaluated Result:", JSON.stringify(evaluatedResult));
    //  console.log("Original Labels Extracted: ", originalLabelsExtracted)
    if (JSON.stringify(evaluatedResult) === JSON.stringify(input))
        return symbolicResult;
    else
        return null;
}

function processBrackets(tokens) {
    const openingBrackets = ['[', '(', '{'];
    const closingBrackets = [']', ')', '}'];
    const matchingBrackets = {
        '[': ']',
        '(': ')',
        '{': '}'
    };

    let stack = []; // Stack to track opening brackets
    let pairs = []; // Array to store pairs of indices for matching brackets

    // Step 1: Find matching brackets
    tokens.forEach((token, index) => {
        if (token[0] === 'bracket') {
            const bracketType = token[1];

            if (openingBrackets.includes(bracketType)) {
                // Push opening bracket onto the stack
                stack.push({
                    type: bracketType,
                    index
                });
            } else if (closingBrackets.includes(bracketType)) {
                // Check if it matches the top of the stack
                if (
                    stack.length > 0 &&
                    matchingBrackets[stack[stack.length - 1].type] === bracketType
                ) {
                    const opening = stack.pop(); // Pop the matching opening bracket
                    pairs.push([opening.index, index]); // Store the pair of indices
                }
            }
        }
    });

    // Step 2: Validate each pair
    const validPairs = pairs.filter(([openIndex, closeIndex]) => {
        // Check that opening bracket is preceded by ["SEPARATOR", ","]
        const hasSeparatorBeforeOpening =
            (openIndex > 0 &&
                tokens[openIndex - 1][0] === 'SEPARATOR' &&
                tokens[openIndex - 1][1] === ',') || (openIndex == 0);

        // Check that closing bracket is followed by ["SEPARATOR", ","]
        const hasSeparatorAfterClosing =
            (closeIndex < tokens.length - 1 &&
                tokens[closeIndex + 1][0] === 'SEPARATOR' &&
                tokens[closeIndex + 1][1] === ',') || (closeIndex == tokens.length - 1);

        // Check that all tokens between the brackets are of allowed types
        const allowedTypes = ['words'];
        const disallowedTypes = ['labelat', 'labeldot'];
        const betweenTokens = tokens.slice(openIndex + 1, closeIndex);
        const allTokensAllowed = betweenTokens.every(
            (token) => allowedTypes.includes(token[0])
        );


        return (
            (hasSeparatorBeforeOpening && hasSeparatorAfterClosing) || (allTokensAllowed && hasSeparatorAfterClosing)
        );
    });

    // Step 3: Flatten and sort indices in descending order
    const indicesToRemove = validPairs.flat().sort((a, b) => b - a);

    // Step 4: Remove tokens at specified indices
    indicesToRemove.forEach((index) => {
        tokens.splice(index, 1); // Remove token at this index
    });

    return tokens;
}

// Helper function to find the index of the next matching closing bracket
function findClosingBracketIndex(array, startIndex, openingBracket) {
    const matchingClosingBracket = getMatchingClosingBracket(openingBracket);
    let depth = 0;

    for (let i = startIndex; i < array.length; i++) {
        const element = array[i];
        if (element[0] === 'bracket') {
            if (element[1] === openingBracket) depth++;
            if (element[1] === matchingClosingBracket) {
                if (depth === 0) return i;
                depth--;
            }
        }
    }

    return -1; // No matching closing bracket found
}

// Helper function to get the matching closing bracket for a given opening bracket
function getMatchingClosingBracket(openingBracket) {
    const pairs = {
        '[': ']',
        '(': ')',
        '{': '}'
    };
    return pairs[openingBracket];
}

// Helper function to check if two brackets match
function isMatchingBracket(opening, closing) {
    const pairs = {
        '[': ']',
        '(': ')',
        '{': '}'
    };
    return pairs[opening] === closing;
}


//////////////////////

function digestHtmlString(htmlString) {
    // Create a DOM parser to parse the HTML string
    const parser = new DOMParser();
    const doc = parser.parseFromString(htmlString, 'text/html');

    // Initialize an array to store the tokens
    const tokens = [];

    // Loop through all child nodes of the body
    doc.body.childNodes.forEach((node) => {
        if (node.nodeName === 'SPAN') {
            // Extract the specific class name after 'token'
            const classList = Array.from(node.classList);
            const tokenType = classList.find((cls) => cls !== 'token'); // Find the class that is not 'token'
            const tokenContent = node.textContent.replace(/\s+/g, ''); // Extract the text content
            tokens.push([tokenType, tokenContent]);
        } else if (node.nodeName === 'BR') {
            // Handle <br> tags as punctuation tokens
            if ((tokens.length==0)||(tokens[tokens.length - 1][1] !== '\n'))
                tokens.push(['punctuation', '\n']);
        }
    });

    return tokens;
}

function groupTokens(tokens) {
    tokens = processBrackets(tokens);
    const grouped = [];
    let currentGroup = [];
    let newGroup = false;
    tokens.forEach((token) => {
        const [type, value] = token;
        if ([',', '\n', ']', '}', ')'].includes(value)) {
            newGroup = false;
            if (currentGroup.length > 0) {
                grouped.push(currentGroup);
                currentGroup = []; // Reset the group
            }
            if (value === '\n')
                grouped.push([token]);
            else if ([']', '}', ')'].includes(value)) {
                currentGroup.push(token);
                //newGroup = false;
            }
        } else {
            // Check if the token should be grouped with the current group
            if (!newGroup) {
                currentGroup.push(token); // Add to the current group
            } else {
                // If the current group is not empty, push it to `grouped`
                if (currentGroup.length > 0) {
                    grouped.push(currentGroup);
                    currentGroup = []; // Reset the group
                }
                // Add the current token as its own subarray
                if (token.length > 0)
                    grouped.push([token]);
                newGroup = false;
            }
            if (['[', '{', '('].includes(value))
                if (currentGroup.length > 0) {
                    grouped.push(currentGroup);
                    currentGroup = []; // Reset the group
                }
        }
    });

    // Push any remaining tokens in `currentGroup` to `grouped`
    if (currentGroup.length > 0) {
        grouped.push(currentGroup);
    }

    return grouped;
}



function areBracketsBalanced(tokens) {
    const openingBrackets = ['[', '{', '(']; // Valid opening brackets
    const closingBrackets = [']', '}', ')']; // Valid closing brackets
    const matchingBrackets = {
        '[': ']',
        '{': '}',
        '(': ')'
    }; // Map of matching pairs

    let stack = []; // Stack to track opening brackets

    for (const token of tokens) {
        if (token[0] === 'bracket') {
            const bracketString = token[1]; // Extract the string containing brackets

            for (const char of bracketString) {
                // Process each character in the string
                if (openingBrackets.includes(char)) {
                    stack.push(char); // Push opening bracket onto the stack
                } else if (closingBrackets.includes(char)) {
                    // Check if the closing bracket matches the top of the stack
                    if (stack.length === 0 || matchingBrackets[stack.pop()] !== char) {
                        return false; // Unbalanced brackets
                    }
                }
            }
        }
    }

    // If the stack is not empty, there are unmatched opening brackets
    return stack.length === 0;
}

function groupRepeats(tokens) {
    //console.log(tokens)
    function groupByLength(tokens, length) {
        const result = [];
        let i = 0;

        while (i < tokens.length) {
            let count = 1;

            // Check for repeated sequences of the given length
            while (
                i + (count + 1) * length <= tokens.length &&
                JSON.stringify(tokens.slice(i, i + length)) ===
                JSON.stringify(tokens.slice(i + count * length, i + (count + 1) * length))
            ) {
                count++;
            }
            let wQ = false;
            let s = [];
            for (let t of tokens.slice(i, i + length))
                for (let tt of t) {
                    s.push(tt);
                    if (tt[0] === 'words')
                        wQ = true;
                }
            if ((count > 1) && wQ && s[0][1] !== '\n' && areBracketsBalanced(s)) {
                // If a repeat is found, replace it with the desired format
                let res1 = tokens.slice(i, i + length);
                let res = [];
                for (let r of res1)
                    if (r.length > 0)
                        res.push(r);
                if (res.length > 0) {
                    //console.log(res);

                    if (res.length > 0) {

                        if (res.length > 1) {
                            result.push(['SEPARATOR', ',']);
                            result.push(['number', count]);
                            result.push(['punctuation', '*']);
                            result.push(['bracket', '[']);
                            result.push(['SEPARATOR', ',']);
                            for (let r of res) {
                                result.push(...r);
                                result.push(['SEPARATOR', ',']);
                            }
                            result.push(['bracket', ']']);
                        } else {
                            result.push(['SEPARATOR', ',']);
                            result.push(['number', count]);
                            if (res[0].length > 1){ //5ch.A[c++] != 5*ch.A[c++] !!!
                                result.push(['punctuation', '*']);
                                result.push(['bracket', '[']);
                                result.push(['SEPARATOR', ',']);
                            }
                            result.push(...res[0]);
                            if (res[0].length > 1){
                                result.push(['SEPARATOR', ',']);
                                result.push(['bracket', ']']);
                            }
                            //if (result[result.length-1][0]!=='words' )
                            //    throw new Error('I failed simplifying '+JSON.stringify(res));
                        }
                    }
                }
                i += count * length;
            } else {
                // console.log(tokens[i])
                // Otherwise, just add the current token
                result.push(['SEPARATOR', ',']);
                for (let t of tokens[i])
                    result.push(t);
                i++;
            }
        }

        return result;
    }

    let maxLength = Math.min(tokens.length, 500); // Limit grouping to up to 4 tokens

    let currentTokens = tokens.filter((t) => t.length > 0); // Filter out empty tokens
    //console.log('0:', currentTokens);
    currentTokens = groupTokens(currentTokens);
    for (let length = 1; length <= maxLength; length++) {
        if (length > 1)
            currentTokens = groupTokens(currentTokens);
        //console.log(length, ' ', JSON.stringify(currentTokens));
        currentTokens = processBrackets(groupByLength(currentTokens, length));
        //console.log(length, ' ', JSON.stringify(currentTokens));
        currentTokens = currentTokens.filter((t) => t.length > 0);
        maxLength = Math.min(maxLength, groupTokens(currentTokens).length)

    }

    return currentTokens;
}

// Extract standalone comment lines/blocks and strip *all* comments from the body.
// Standalone comments are:
//   - Lines that start with '#'
//   - Blocks enclosed by backslashes (\ ... \) that start at the beginning of a line
//     (after optional whitespace) and end at the end of a line (before optional whitespace).
// Inline comments (e.g. "sc,dc #..." or "sc,dc \...\") are stripped entirely.
function extract_standalone_comments_and_strip(text) {
    text = String(text == null ? '' : text);
    // Normalize CRLF -> LF for internal processing.
    text = text.replace(/\r\n/g, '\n').replace(/\r/g, '\n');

    let comments = [];
    let body = '';

    let i = 0;
    let lineStart = 0;              // index into original text
    let bodyLenAtLineStart = 0;     // index into `body`

    let inSlash = false;
    let slashCollect = false;
    let slashLineStart = 0;

    while (i < text.length) {
        const ch = text[i];

        if (inSlash) {
            if (ch === '\\') {
                // Closing delimiter.
                inSlash = false;

                const end = i;
                let eol = text.indexOf('\n', end + 1);
                if (eol === -1) eol = text.length;
                const suffix = text.slice(end + 1, eol);

                if (slashCollect && suffix.trim() === '') {
                    // Standalone \...\ block -> collect and remove entire line (including newline).
                    let chunk = text.slice(slashLineStart, eol).replace(/\s+$/g, '');
                    if (chunk !== '') comments.push(chunk);

                    // Skip to after the newline.
                    i = eol;
                    if (i < text.length && text[i] === '\n') i++;
                    lineStart = i;
                    bodyLenAtLineStart = body.length;
                    continue;
                }
            }
            // Strip everything inside a \...\ comment, including newlines.
            i++;
            continue;
        }

        // Not in a \...\ comment.
        if (ch === '\\') {
            // Opening delimiter.
            const prefix = text.slice(lineStart, i);
            slashCollect = (prefix.trim() === '');
            slashLineStart = lineStart;
            if (slashCollect) {
                // Remove leading whitespace already copied to body on this line.
                body = body.slice(0, bodyLenAtLineStart);
            }
            inSlash = true;
            i++;
            continue;
        }

        if (ch === '#') {
            const prefix = text.slice(lineStart, i);
            let eol = text.indexOf('\n', i);
            if (eol === -1) eol = text.length;

            if (prefix.trim() === '') {
                // Standalone # comment line -> collect and remove entire line (including newline).
                body = body.slice(0, bodyLenAtLineStart);
                let chunk = text.slice(lineStart, eol).replace(/\s+$/g, '');
                if (chunk !== '') comments.push(chunk);
                i = eol;
                if (i < text.length && text[i] === '\n') i++;
                lineStart = i;
                bodyLenAtLineStart = body.length;
                continue;
            }

            // Inline # comment -> strip to end-of-line (but keep the newline).
            i = eol;
            continue;
        }

        // Normal character.
        body += ch;
        if (ch === '\n') {
            lineStart = i + 1;
            bodyLenAtLineStart = body.length;
        }
        i++;
    }

    // Unterminated \... comment: parse treats it as comment-to-EOF.
    if (inSlash && slashCollect) {
        body = body.slice(0, bodyLenAtLineStart);
        let chunk = text.slice(slashLineStart).replace(/\s+$/g, '');
        if (chunk !== '') comments.push(chunk);
    }

    // Build header, ensuring exactly one newline between header and body when both exist.
    let header = comments.map(c => String(c).replace(/\n+$/g, '')).join('\n');
    header = header.replace(/\n+$/g, '');
    let strippedBody = body;
    strippedBody = strippedBody.replace(/^\n+/g, '');
    if (header.trim() !== '') header = header + '\n';
    return { header: header, body: strippedBody };
}

// Extract directive lines that must not be simplified/whitespace-stripped.
// These lines are removed from the body and returned as a header block. Each directive
// line is trimmed only at the ends, preserving internal whitespace.
//
// Directives include:
//   DOT:
//   INDEX_ARRAY:
//   SORT_LABEL:
//   TRANSFORM_OBJECT:
//   BACKGROUND:
function extract_dot_lines(text) {
    text = String(text == null ? '' : text);
    // Normalize CRLF -> LF for internal processing.
    text = text.replace(/\r\n/g, '\n').replace(/\r/g, '\n');

    const dots = [];
    const kept = [];

    const DIRECTIVES = ['DOT:', 'INDEX_ARRAY:', 'SORT_LABEL:', 'TRANSFORM_OBJECT:', 'BACKGROUND:'];

    for (const line of text.split('\n')) {
        const ls = line.trimStart();
        if (DIRECTIVES.some(p => ls.startsWith(p))) {
            const trimmed = line.trim(); // trim only ends; keep internal whitespace
            if (trimmed !== '') dots.push(trimmed);
        } else {
            kept.push(line);
        }
    }

    // Build header, ensuring exactly one newline between header and body when both exist.
    let header = dots.join('\n');
    header = header.replace(/\n+$/g, '');
    let body = kept.join('\n');
    body = body.replace(/^\n+/g, '');
    if (header.trim() !== '') header = header + '\n';
    return { header: header, body: body };
}


function cleanString(input) {
    if (typeof input !== "string") {
        throw new Error("Input must be a string");
    }

    // Step 1: Replace repeated new lines with a single new line
    let result = input.replace(/\n+/g, "\n");

    // Step 2: Remove trailing and leading white spaces (but keep new lines intact)
    result = result.replace(/[ \t]+/g, "");

    // Step 2.5: Ensure DOT directives start on their own line.
    // Simplification can accidentally leave a comma immediately before 'DOT:' (e.g., '],DOT:start=5'),
    // which breaks parsing because DOT directives must be on their own line.
    result = result.replace(/,DOT:/g, "\nDOT:");
    // Also guard against the rare case where 'DOT:' is stuck to the end of a token without a newline.
    //result = result.replace(/(^|[^\n])DOT:/g, (m, p1) => (p1 ? (p1 + "\nDOT:") : "DOT:"));


    // Step 3: Replace repeated commas with a single comma
    result = result.replace(/,+/g, ",");

    // Step 4: Remove commas in specific combinations
    const patternsToRemoveComma = [
        /\[,/g, // '[,'
        /\{,/g, // '{,'
        /\(,/g, // '(,'
        /,\]/g, // ',]'
        /,\)/g, // ',)'
        /,\}/g, // ',}'
        /,\n/g, // ',\n'
        // /,@/g, // ',\n'
        // /,\./g, // ',\n'
        /^\,+/, // Comma at the start of the string
        /\,+$/, // Comma at the end of the string
        /\n,/g // New line followed by a comma
    ];

    patternsToRemoveComma.forEach(pattern => {
        result = result.replace(pattern, match => match.replace(",", "")).replace(/\n+/g, "\n");;
    });
    
    // Step 5: Ensure newline at the end
    if (!result.endsWith("\n")) {
        result += "\n";
    }

    return result;
}

function collectExpression() {
    // Create a dialog box
    var dialog = document.createElement('div');
    dialog.style.cssText = 'position:fixed;top:50%;left:50%;transform:translate(-50%,-50%);background:white;padding:20px;border:1px solid black;z-index:1000;';

    // Warning message
    var warning = document.createElement('p');
    warning.style.cssText = 'font-weight:700;'
    warning.textContent = "Warning!!!";

    dialog.appendChild(warning);

    var warning1 = document.createElement('p');
    warning1.style.cssText = ''
    warning1.textContent = "This will overwrite your instructions with their simplified form. For example, [sc,dc],[sc,dc],[sc,dc] will be replaced with 3[sc,dc]. This tool is EXPERIMENTAL and may break your instructions!";

    dialog.appendChild(warning1);

    var warning2 = document.createElement('p');
    warning2.style.cssText = 'font-weight:700;'
    warning2.textContent = "Save your work before continuing!";

    dialog.appendChild(warning2);

    // Questions and answers
    var questionsAndAnswers = [
        ["1 + 1 = ?", 2],
        ["2 + 2 = ?", 4],
        ["3 + 3 = ?", 6],
        ["4 + 4 = ?", 8],
        ["8 + 1 = ?", 9],
        ["3 + 6 = ?", 9],
        ["6 + 2 = ?", 8],
        ["1 + 1 = ?", 2],
        ["2 + 1 = ?", 3],
        ["3 + 2 = ?", 5],
        ["4 - 2 = ?", 2],
        ["5 - 3 = ?", 2],
        ["2 + 3 = ?", 5],
        ["6 - 4 = ?", 2],
        ["3 + 4 = ?", 7],
        ["7 - 5 = ?", 2],
        ["4 + 3 = ?", 7],
    ];
    var index = Math.floor(Math.random() * questionsAndAnswers.length);
    var [question, correctAnswer] = questionsAndAnswers[index];


    // Checkbox for "Expand before simplification?"
    var expandExprCheckboxContainer = document.createElement('div');
    expandExprCheckboxContainer.style.marginTop = '10px';

    var expandExprCheckboxLabel = document.createElement('label');
    expandExprCheckboxLabel.textContent = "Expand before simplification?";
    expandExprCheckboxLabel.style.marginRight = '10px';

    var expandExprCheckbox = document.createElement('input');
    expandExprCheckbox.type = 'checkbox';
    expandExprCheckbox.checked = false; // Default unchecked

    // Variable to store the checkbox state
    var expandExpr = false;

    // Update expandExpr based on checkbox state
    expandExprCheckbox.onchange = function() {
        expandExpr = expandExprCheckbox.checked;
    };

    expandExprCheckboxContainer.appendChild(expandExprCheckboxLabel);
    expandExprCheckboxContainer.appendChild(expandExprCheckbox);
    dialog.appendChild(expandExprCheckboxContainer);


    /////


    var expandExprCheckboxContainer1 = document.createElement('div');
    expandExprCheckboxContainer1.style.marginTop = '10px';

    var expandExprCheckboxLabel1 = document.createElement('label');
    expandExprCheckboxLabel1.textContent = "Attempt to simplify numerical indexing of labels and create index counters? The code will try to replace expressions such as ch.A[0],ch.A[1],ch.A[2],ch.A[3] with ch.A[$vara=0$vara],3*ch.A[++vara]. ";
    expandExprCheckboxLabel1.style.marginRight = '10px';

    var expandExprCheckbox1 = document.createElement('input');
    expandExprCheckbox1.type = 'checkbox';
    expandExprCheckbox1.style.marginTop = '10px';
    expandExprCheckbox1.checked = false; // Default unchecked

    // Variable to store the checkbox state
    var expandExpr1 = false;

    // Update expandExpr based on checkbox state
    expandExprCheckbox1.onchange = function() {
        expandExpr1 = expandExprCheckbox1.checked;
    };

    expandExprCheckboxContainer1.appendChild(expandExprCheckboxLabel1);
    expandExprCheckboxContainer1.appendChild(expandExprCheckbox1);
    dialog.appendChild(expandExprCheckboxContainer1);

    /////

    var questionElem = document.createElement('p');
    questionElem.textContent = "If you want to continue, please answer this question by entering a number:";
    dialog.appendChild(questionElem);

    var questionElem1 = document.createElement('p');
    questionElem1.textContent = question;
    questionElem1.style.marginBottom = '10px';
    dialog.appendChild(questionElem1);

    var input = document.createElement('input');
    input.type = 'number';
    dialog.appendChild(input);

    var buttonContainer = document.createElement('div');
    buttonContainer.style.marginTop = '10px';

    var okButton = document.createElement('button');
    okButton.textContent = 'OK';
    okButton.disabled = true; // Initially disabled
    okButton.onclick = function() {
        document.body.removeChild(dialog);
        proceedWithExpansion();
    };
    buttonContainer.appendChild(okButton);

    var cancelButton = document.createElement('button');
    cancelButton.textContent = 'Cancel';
    cancelButton.onclick = function() {
        document.body.removeChild(dialog);
    };
    buttonContainer.appendChild(cancelButton);

    dialog.appendChild(buttonContainer);

    // Enable OK button only when the correct answer is provided
    input.oninput = function() {
        okButton.disabled = (parseInt(input.value) !== correctAnswer);
    };

    document.body.appendChild(dialog);

    function proceedWithExpansion() {
        var inputText = document.getElementById("inputText");
        var inputhtml = document.getElementById("highlighting");
        // Preserve standalone comment lines/blocks by moving them to the top,
        // strip *all* inline comments, then pull out DOT: lines (preserving their internal whitespace)
        // and move them to the top (after comments).
        const extracted = extract_standalone_comments_and_strip(inputText.value);
        const commentHeader = extracted.header;
        const extractedDots = extract_dot_lines(extracted.body);
        const dotHeader = extractedDots.header;
        let workText = extractedDots.body;

        if (expandExpr) {
            inputText.value = cleanString(evaluate_indices_and_stop(workText, false));
            console.log(inputText.value);
            inputText.value = cleanString(evaluate_indices_and_stop(inputText.value, false));
            console.log(inputText.value);
        } else
            inputText.value = cleanString(workText);
       
        update(inputText.value);
        onMyInput();
        //console.log(groupTokens(digestHtmlString(inputhtml.innerHTML)))
        let labels = [];
        let tokens0 = digestHtmlString(inputhtml.innerHTML);
        let tokens = [];
        for (let t of tokens0) {
            if (t[1] !== ',' && t[0] !== 'comment') {
                if (['[', '(', '{'].includes(t[1])) {
                    tokens.push(t);
                    tokens.push(['SEPARATOR', ',']);
                } else if ([']', ')', '}'].includes(t[1])) {
                    tokens.push(['SEPARATOR', ',']);
                    tokens.push(t);
                } else if (t[1]==='\n'){
                    tokens.push(['SEPARATOR', ',']);
                    tokens.push(t);
                    tokens.push(['SEPARATOR', ',']);
                }
                    else
                    tokens.push(t);
            } else if (t[0] !== 'comment')
                tokens.push(['SEPARATOR', ',']);
            if (['labelat', 'labeldot'].includes(t[0]))
                labels.push(t);
        }
        let Xs = processLabels(labels);
        if (Xs !== null && expandExpr1) {
            let [labelsToWorkWith, processedLabels] = Xs;
            // Assuming tokens and processedLabels are already defined
            let k = 0;
            if (labelsToWorkWith.length > 0 && labelsToWorkWith.length == processedLabels.length) {
                for (let i = 0; i < tokens.length; i++) {
                    if (tokens[i][0] === 'labelat' || tokens[i][0] === 'labeldot') {
                        if (processedLabels.length > 0) {
                            if (tokens[i][1] === labelsToWorkWith[k]) {
                                k++;
                                tokens[i][1] = processedLabels.shift(); // Replace the token with processed label
                            }
                            // Remove first element
                        } else {
                            // Handle the case where there are more labels than processed labels, if needed
                            console.warn("More labels than processed labels.  Check your logic.");
                        }
                    }
                }
            }
        }
        console.log(JSON.stringify(labels));
        //console.log('first', JSON.stringify(tokens))
        tokens = processBrackets(groupRepeats(tokens));

        //inputText.value =         removeUnnecessaryBrackets(tokens).map(token => token[1]).join('');

        inputText.value = commentHeader + dotHeader + cleanString(tokens.map(token => token[1]).join(''));
        inputText['expanded']=false;
        
        update(inputText.value);
        onMyInput();
    }
}
