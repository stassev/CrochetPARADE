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


function generate_sphere(Ncirc,scatter=true,Nlat=-1) {
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
  let count = Math.max(Math.ceil(list.length / 18),(list.length > 18*4 ?Math.ceil(longestConsecutiveSC(list)/4):0)) * (Si % 3)  + (list.length > 18*4 ? Si : 0);
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
  if (Nlat==-1) 
    Nlat = ceiling((Ncirc / 2) + 1);
  if ((Nlat%2)==1)
    Nlat+=1;
  if (Ncirc<20)
    Nlat-=1;
  if(Ncirc<10){
    Nlat-=1;
    if (Nlat<3)
      Nlat=2;
  }
  if(Ncirc<7)
    throw new Error("Ncirc should be >=7")
  const lat = range(0, Nlat).map(i => (i / Nlat) * Math.PI);
  const icirc = lat.map(l => floor(Math.sin(l) * Ncirc+1.e-7));
  icirc[0] = 1;
  icirc[icirc.length - 1] = 1;

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
  in_[0][0] += "@R";
  //console.log(in_)
  const out0 = in_.map(replaceSequence);
  const out = out0.map(distributeEvenly);
  let outA=out;
  if (scatter)
     outA = out.map(cyclicPermuteBySC);

  const out2 = "ring.R\n" + listToString(outA);
  console.log(out2)
  const out3 = rewritePattern(out2);
  const out4 = combineRepeatedSeries(out3);

  return out4.replace(/\*s/g, "s");
}
