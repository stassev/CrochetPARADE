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


var EXTRA_DOTS = '';
var backgroundColor = '';

var textBLFLtest = `10ch,turn
ch,sk,9sc,turn
ch,sk,9scbl,turn
ch,sk,9scbl,turn
ch,sk,9scfl,turn
DOT:iterations=2000
DOT: learning_rate=0.05`;

var textMosaic = `#To see the mosaic pattern, first click on the 3D model.
#Then press 'c' to show the colors.
#Then increase the yarn thickness by pressing 'ctrl+=' 3 times, 
#which will double the thickness.

#Define a dropped double-crochet that is attached to the front loop.
#The 2 in 2B below defines the attachment depth level (see the Manual).
DEF: drop_dc=&drop_dc^A(drop_dc):2B[front]~A-B::!-1-A;B-2.1-A

COLOR:white
33ch
start_at@[-1,0],ch,32sc
start_at@[-1,1],ch,32sc
COLOR:green,start_at@[-1,1],ch,[drop_dc,5scbl]*5,drop_dc,scbl
COLOR:white,start_at@[-1,1],ch,scbl,[drop_dc,5scbl]*5,drop_dc
COLOR:green,start_at@[-1,1],ch,2scbl,[drop_dc,5scbl]*5
COLOR:white,start_at@[-1,1],ch,3scbl,[drop_dc,4scbl,>,scbl]*5
COLOR:green,start_at@[-1,1],ch,4scbl,[drop_dc,3scbl,>,2scbl]*5
COLOR:white,start_at@[-1,1],ch,5scbl,[drop_dc,2scbl,>,3scbl]*5
COLOR:green,start_at@[-1,1],ch,[drop_dc,5scbl]*5,drop_dc,scbl
COLOR:white,start_at@[-1,1],ch,[drop_dc,5scbl]*5,drop_dc,scbl
COLOR:green,start_at@[-1,1],ch,scbl,[drop_dc,5scbl]*5,drop_dc
COLOR:white,start_at@[-1,1],ch,2scbl,[drop_dc,5scbl]*5
COLOR:green,start_at@[-1,1],ch,3scbl,[drop_dc,4scbl,>,scbl]*5
COLOR:white,start_at@[-1,1],ch,4scbl,[drop_dc,3scbl,>,2scbl]*5
COLOR:green,start_at@[-1,1],ch,5scbl,[drop_dc,2scbl,>,3scbl]*5
DOT: start=3`;

var textLacyHat = `# Lacy hat showcase
# Own design, incorporating a modified version of the flower in the "Irish crochet flower 1" showcase.
# Needs more work -- possibly make the dome larger, and close up the largest holes on the side. But
# I think it's good enough for a demo, showing a mixture of styles.
#
# Start with Irish crochet style flower petals
DEF: p=3ch,ss@1[%,%-4] # Picot stitch: chain 3, then slip-stitch to stitch at base of picot
DEF: dc=Copy(dc,2)
COLOR: rgb(240,180,150)
6ch.Ring+1!,ss@[%,0]
[ch,15sc].Ring1[]@Ring,ss@[%,0]
ch,sk,sc,[2sc,<,p]*8,ss@[%,0],sc@Ring1[][0]
$c=0$,@Ring1[][0],[5ch.chain_space[0,c++]+!,sk,>,sc]*8,ss@[-1,-1]
$t=0,c=0$,ch,[sc,hdc,dc,p,tr.Tip[t++],dc,p,hdc,>,sc]@chain_space[0,c++]*8,ss@[%,0]
$t=0$,start_at@Tip[t]
$k=0$,[ss@Tip[t++],7ch.chsp[0,k++]]*8,sc@[%,0]
$k=0$,ch,[sc,2hdc,2dc,1tr,2dc,2hdc,>,sc]@chsp[0,k++]*8,ss@[%,0]
$k=0$,sk,6ss,[10ch.chsp[1,k++],>,ss@[tr:@+1]]*8,sc@[%,5]
$k=0$,ch,[2sc,2hdc,3dc,tr,3dc,2hdc,sc,>,sc]@chsp[1,k++]*8,ss@[%,0]
$k=0$,sk,8ss,[13ch.chsp[2,k++],>,ss@[tr:@+1]]*8,sc@[%,7]
#Switch to filet crochet
7sk,2ss,2ch,[[2sk,2ch,dc]*4,sk,2ch,>,dc]*8,ss@[ch:%,1]
4sk,ss,2ch,[2sk,2ch,>,dc]*40,ss@[ch:%,1]
3sk,ss,2ch,[2sk,2ch,>,dc]*40,ss@[ch:%,1]
#Switch to crocheting in the round
3sk,sc,119sc
[4sc,sc2tog]*20
[3sc,sc2tog]*20
[80sc
]*5
79sc,ss@[%,0]
`;

var textEdging = `#Edging showcase
DEF: hdc=Copy(hdc,2) # Change height of hdc
DEF: dc=&dc^A(dc):B~A-B:C;D:!-1-A;B-1-C;C-1-D;D-1-A #fancy dc
DEF: fan_bottom=2sc,3sk,7ch.C[k++]+!,3sc
DEF: dc_headless=&headless dc^:B~:C;D:B-1-C;C-1-D;D-1-! #fancy dc
DEF: some_space=&leaves some space in chain space^:B~::
DEF: fan_top=4dc_headless@C[--k],3ch,[some_space,dc4tog,some_space]@C[k],3ch,dc4tog@C[k]
DEF: fan_top_beginning=dc4tog@C[--k],3ch,[some_space,dc4tog,some_space]@C[k],3ch,dc4tog@C[k]
ch,4*(8ch),ch,turn
sk,4*(8sc),sc,ch,turn
$k=0$,sk,sc,fan_bottom*4,3ch,turn
4sk,fan_top_beginning,fan_top*3,3ch,ss,turn
sk,[ss,<,ch,hdc,hdc,(3ch,ss@1[%,-4]),hdc,ch]*10,ss
DOT: start=10`;

var textFlower3 = `# Flower showcase, demonstrating stitches in the post of a stitch.
#Change default heights of stitches:
DEF: dc=Copy(dc,3)
DEF: hdc=Copy(hdc,2)
COLOR: Yellow
11ch,ss@[%,0]
COLOR: Blue
$k=0$,3ch.A[11]+!,(3ch,sk,>,dc.A[k++]^!,dc@[@].A[k++]^!)*6,dc.A[k++]^!,ss@[%,2]
COLOR: Red
$k=0$,@[-1,0],ch,[3ch,sc@[dc:@+1],[hdc,2dc,hdc]@A[k++]~,[hdc,2dc,hdc]@A[k++],>,sc@[dc:@]]*6,sc@[-1,-1]
DOT: start=37`;

var textSquare = `#Granny square showcase
# Own design, incorporating a modified version of the flower in the "Irish crochet flower 1" showcase.
DEF: p=3ch,ss@1[%,%-4] # Picot stitch: chain 3, then slip-stitch to stitch at base of picot
COLOR: Pink
6ch.Ring+1!,ss@[%,0]
[ch,15sc].Ring1[]@Ring,ss@[%,0]
ch,sk,sc,[2sc,<,p]*8,ss@[%,0],COLOR: Violet,sc@Ring1[][0]
$c=0$,@Ring1[][0],[5ch.chain_space[0,c++]+!,sk,>,sc]*8,ss@[-1,-1]
$t=0,c=0$,ch,[sc,hdc,dc,p,tr.Tip[t++],dc,p,hdc,>,sc]@chain_space[0,c++]*8,ss@[%,0]
COLOR: Green
# This starts a new yarn with chain-3 then 3dc together in base to form a starting dc-4 bobble:
DEF: dc4bobble_start_new= &a dc bobble of 4 stitches^B(hidden);C(ch);D(ch),A(dc):B1~A-B1:E;F;G;H;I;J:!-skip-B;B1-0.001-B;B-0.7-C;C-0.8-D;D-0.7-A;B-0.7-E;E-0.8-F;F-0.7-A;B-0.7-G;G-0.8-H;H-0.7-A;B-0.7-I;I-0.8-J;J-0.7-A
$t=0,c=0$,dc4bobble_start_new@Tip[t],[dc4bobble@Tip[t],<,2ch.chsp[c++]+!,tr4bobble@Tip[t],2ch.chsp[c++]+!,dc4bobble@Tip[t],4ch.chsp[c++]+!,hdc@Tip[++t],4ch.chsp[c++]+!,$t++$]*4,sc@[%,3]
COLOR: Pink
$c=0$,3ch,[3tr@chsp[c++],3ch,3tr@chsp[c++],ch,>,(4dc@chsp[c++],ch)*2]*4,4dc@chsp[c++],ch,3dc@chsp[c++],ss@[%,1]
COLOR: Green
ch,2sk,5sc,[sc,dc@[@],sc@[@],13sc,>,6sc]*4,ss@[%,0]
DOT: start=1
`;

var textTestEdgeOfSpaces1 = `10ch,turn
sk,9sc,turn
ch,2sc,4ch.A,4sk,3sc,turn
4ch,5sc@A,4ch,sc`;

var textTestEdgeOfSpaces2 = `10ch,turn
sk,9sc,turn
ch,2sc,4ch.A!1,4sk,3sc,turn
4ch,3sc@A,4ch,sc`;

var textTestEdgeOfSpaces3 = `10ch,turn
sk,9sc,turn
ch,2sc,4ch.A!,4sk,3sc
4ch,3sc@A,4ch,sc`;

var textSwatch = `#Swatch showcase
21ch,turn
sk,20ss,turn
ch,20ss,turn
ch,20ss,turn
ch,sk,19sc,turn
ch,sk,19sc,turn
ch,sk,19sc,turn
2ch,sk,19hdc,turn
2ch,sk,19hdc,turn
2ch,sk,19hdc,turn
3ch,sk,19dc,turn
3ch,sk,19dc,turn
3ch,sk,19dc,turn
4ch,sk,19tr,turn
4ch,sk,19tr,turn
4ch,sk,19tr,turn
# Pattern with single crochet increases
ch,sc,(sk,sc2inc)*9,sk,sc,turn
ch,sc,(sk,sc2inc)*9,sk,sc,turn
ch,sc,(sk,sc2inc)*9,sk,sc,turn
ch,sc,(sk,sc2inc)*9,sk,sc,turn
ch,sc,(sk,sc2inc)*9,sk,sc,turn
# Pattern with single crochet 2 together
2ch,sk,(sc3tog,ch,@[@-1])*8,sc3tog,ch,sc,turn
# ... which is equivalent to:
2ch,sk,(sc3tog,ch,>,@[@-1])*9,sc,turn
# ... which is equivalent to:
2ch,sk,sc3tog,ch,(sc3tog@[@],ch)*8,sc,turn
2ch,sk,sc3tog,ch,(sc3tog@[@],ch)*8,sc,turn
# Crossed double crochet
3ch,2sk,dc,(dc@[@-1],dc@[@+3])*8,dc@[@-1],dc@[@+2],turn
3ch,2sk,dc,(dc@[@-1],dc@[@+3])*8,dc@[@-1],dc@[@+2],turn
# Equivalently, we can define a crossed double crochet stitch:
DEF: crdc=dc@[@-1],dc@[@+3]
3ch,2sk,dc,8crdc,dc@[@-1],dc@[@+2],turn
# Equivalently, we can use two attachment heads @ and @1
3ch,2sk,dc,dc@1[@-1],(dc@[@+2],dc@1[@1+2])*8,dc,turn
# Equivalently, we can define a crossed double crochet stitch with the raw stitch grammar:
DEF: crdc_v2=&crdc_v2^A(dc);B(dc):C;D~A-D;B-C::!-1-A;A-1-B;C-2-B;D-2-A
3ch,sk,9crdc_v2,dc,turn
#Note how the above stitch instructions simplified.
# Below is a bobble of 3 sc stitches
ch,sk,sc,[sc3bobble,sc]*9,turn
# Now repeat same line 4 times. Note new line at the end:
[ch,sk,sc,[sc3bobble,sc]*9,turn
]*4
#dc3-, dc4-,dc5-bobble:
2ch,sk,dc,[dc3bobble,dc]*9,turn
2ch,sk,dc,[dc4bobble,dc]*9,turn
2ch,sk,dc,[dc5bobble,dc]*9,turn
# now popcorns:
2ch,sk,dc,[dc3pc,dc]*9,turn
2ch,sk,dc,[dc4pc,dc]*9,turn
2ch,sk,dc,[dc5pc,dc]*9,turn
ch,sk,19sc,turn
# And here is a funky stitch that jumps over rows
DEF: funky=&funky^A(funky):B;2C;D~A-D::!-1-A;B-1-A;C-3-A;D-1-A
[2ch,sk,[hdc,ch,funky,ch]*4,3hdc,turn
ch,sk,19sc,turn
]*4
`;

var textTestFunky = `DEF: funky=&funky^A(funky):B;2C;D~A-D::!-1-A;B-1-A;C-1-A;D-1-A
9ch,turn
9sc,turn
9sc,turn
3sc,funky,sc`;

var textChainSpaceTest = `9ch,turn
9sc,turn
ch,@[-1,-1],2sc,4ch.A,3sc,turn
2ch,sc,3sc@A,ch,sc`;

var textChainSpaceTest1 = `9ch
9sc
ch,@[-1,0],2sc,4ch.A,3sc
2ch,sc,3sc@A,ch,sc`;

var textChainSpaceTest2 = `9ch
9sc
ch,@[-1,0],2sc,3ch.A,3sc
2ch,sc,3sc@A,ch,sc`;

var textChainSpaceTest3 = `9ch
9sc
ch,@[-1,0],2sc,3ch.A,3sc
2ch,sc,4sc@A,ch,sc`;

var textChainSpaceTest4 = `9ch
9sc
ch,@[-1,0],2sc,2ch.A,3sc
2ch,sc,sc@A,ch,sc`;

var textTestAt01 = `9ch,turn
9sc,turn
ch,@[-1,-2],sc`;

var textTestAt02 = `9ch
9sc
ch,@[-1,-2],sc`;

var textTestAt03 = `9ch
9sc
ch,2sc,@[%,0],sc`;

var textTestAt04 = `9ch
9sc
ch,sc,sc@[%,0]`;

//parse_StitchCodeList(parse_original_text_to_list_of_structures(parse_definitions(textTestAt1).replace(/ |\t/g, '')))
//LIST = parse_original_text_to_list_of_structures(text.replace(/ |\t/g, ''))
//parse_StitchCodeList(LIST)

var textTestAt1 = `9ch,turn
2dc,2sc,dc,sc,2dc,turn
sc,dc,tr@[sc:@-1],dc`; //attach at 1,5=14;;
var textTestAt2 = `9ch,turn
2dc,2sc,dc,sc,2dc,turn
sc,dc,tr@[sc:@],dc`; //attach at 1,5=14;;
var textTestAt3 = `9ch,turn
2dc,2sc,dc,sc,2dc,turn
sc,dc,tr@[sc:@+1],dc`; //attach at 1,5=14;;
var textTestAt4 = `9ch,turn
2dc,2sc,dc,sc,2dc,turn
sc,dc,tr@[sc:@+2],dc`; //attach at 1,3=12;;

var textTestAt10 = `9ch
2dc,2sc,dc,sc,2dc
sc,dc,tr@[sc:@-1],dc`; //attach at 1,2=11;;
//parse_StitchCodeList(parse_original_text_to_list_of_structures(parse_definitions(textTestAt10).replace(/ |\t/g, '')))
//parse_StitchCodeList(parse_original_text_to_list_of_structures(parse_definitions(textTestAt10).replace(/ |\t/g, ''))).slice(-2,-1)[0].id_attach
var textTestAt20 = `9ch
2dc,2sc,dc,sc,2dc
sc,dc,tr@[sc:@],dc`; //attach at 1,2=11;;
var textTestAt30 = `9ch
2dc,2sc,dc,sc,2dc
sc,dc,tr@[sc:@+1],dc`; //attach at 1,2=11;;
var textTestAt40 = `9ch
2dc,2sc,dc,sc,2dc
sc,dc,tr@[sc:@+2],dc`; //attach at 1,3=12;;

var textTestAt11 = `9ch,turn
2dc,2sc,dc,sc,2dc,turn
sc,2dc,tr@[sc:@-1],dc`; //attach at 1,5=14;;
var textTestAt21 = `9ch,turn
2dc,2sc,dc,sc,2dc,turn
sc,2dc,tr@[sc:@],dc`; //attach at 1,5=14;;
var textTestAt31 = `9ch,turn
2dc,2sc,dc,sc,2dc,turn
sc,2dc,tr@[sc:@+1],dc`; //attach at 1,3=12;;
var textTestAt41 = `9ch,turn
2dc,2sc,dc,sc,2dc,turn
sc,2dc,tr@[sc:@+2],dc`; //attach at 1,2=11;;


var textTestAt12 = `9ch
2dc,2sc,dc,sc,2dc
sc,2dc,tr@[sc:@-1],dc`; //attach at 1,2=11;;
var textTestAt22 = `9ch
2dc,2sc,dc,sc,2dc
sc,2dc,tr@[sc:@],dc`; //attach at 1,2=11;;
var textTestAt32 = `9ch
2dc,2sc,dc,sc,2dc
sc,2dc,tr@[sc:@+1],dc`; //attach at 1,3=12;;
var textTestAt42 = `9ch
2dc,2sc,dc,sc,2dc
sc,2dc,tr@[sc:@+2],dc`; //attach at 1,5=14;;

var textTestAt33 = `9ch,turn
2dc,2sc,dc,sc,2dc,turn
sc,2dc,tr@[sc:-1,2],dc`; //attach at 1,2=11;;
var textTestAt43 = `9ch
2dc,2sc,dc,sc,2dc
sc,2dc,tr@[sc:-1,2],dc`; //attach at 1,5=14;;

var textTestAttachIndexChain = `9ch
3sc,3ch,sc`;


var textSwatch1 = `10ch,turn
ch,10sc,turn
ch,sk,9sc,turn
ch,sk,9sc,turn
ch,sk,sc,[cl3,sc]*4,turn
ch,sk,9sc,turn
2ch,sk,9hdc,turn
2ch,sk,9hdc,turn
2ch,sk,9hdc,turn
2ch,sk,9hdc,turn
3ch,sk,9dc,turn
3ch,sk,9dc,turn
3ch,sk,9dc,turn
DEF: funky=&funky^A(funky):B;2C;D~A-D::!-1-A;B-1-A;C-3-A;D-1-A
3ch,sk,3dc,funky,3dc,turn
3ch,sk,7dc,turn
`;

var textStocking = `#Stocking showcase
# adjust stitch heights:
DEF: dc=Copy(dc,1.8)
DEF: hdc=Copy(hdc,1.3)
# double-crochet 3-popcorn:
DEF: dc3pc=&dc3pc^A(dc3pc):B~A-B:C;D(dc);E;F(dc);G;H(dc):!-1-A;B-1.2-C;C-1.2-D;B-1-E;E-1-F;B-1.2-G;G-1.2-H;!-0.8-D;D-0.8-F;F-0.8-H;!-0.33-D;D-0.33-H;H-0.33-A
# slip stitch through two disjoint stitches simultaneously
DEF: ss0=&ss0^:B~::B-0.5-!
DEF: ss1=&ss1^A(ss2tog):B~A-B::!-1-A;B-0.5-A
DEF: ss2tog=ss1@[@+1],ss0@1[@1-1]
# Toe:
COLOR: Crimson
8ch,turn
sk,(hdc2inc,5hdc,hdc5inc).R,turn
(hdc@[0,1],4*hdc,hdc2inc).R,ss@[0,-1]
ch,(hdc2inc,7hdc,3hdc2inc,7hdc,hdc2inc)@R,hdc@[-1,-1],ss@[%,0]
ch,hdc,hdc2inc,9hdc,4hdc2inc,9hdc,2hdc2inc,ss@[%,0]
ch,sk,33sc,ss@[ch:%,0]
# Foot:
COLOR: Dark Olive Green
ch,sk,33hdc,ss@[ch:%,0]
ch,sk,[ch,2sk,<,33hdc,ss@[ch:%,0]
2ch,sk,{dc3pc,>,dc}*17,ss@[%,1]
]*6
ch,2sk,33hdc,ss@[ch:%,0]
ch,sk,15hdc.Z,hdc.Q1,17hdc,ss@[ch:%,0].Q2,turn
## Heel:
COLOR: Crimson
sk,sc.A1,15sc,sc2tog.A2,turn
sk,sc.B1,13sc,sc2tog.B2,turn
sk,sc.C1,11sc,sc2tog.C2,turn
sk,sc.D1,9sc,sc2tog.D2,turn
sk,sc.E1,7sc,sc2tog.E2,turn
sk,sc,5sc,sc2tog,sc@E1,turn
@[-1,-2],6sc,ss@E2,sc@D1,turn 
sc@[-1,-3],6sc,sc@E1,ss@D2,sc@C1,turn
sc@[-1,-3],8sc,sc@D1,ss@C2,sc@B1,turn
sc@[-1,-3],10sc,sc@C1,ss@B2,sc@A1,turn
sc@[-1,-3],12sc,sc@B1,ss@A2,sc.S@Q1,turn
sc@[-1,-3],14sc,sc@A1,ss@Q2
COLOR: Dark Olive Green
15hdc@Z,hdc@Q1,hdc@S,hdc@[-1,0],15hdc,ss@[-1,-1]
ch,[ch,2sk,<,33hdc,ss@[ch:%,0]
2ch,sk,{dc3pc,>,dc}*17,ss@[%,1]
]*2
ch,2sk,33hdc.R[],ss@[ch:%,0]
# Cuff:
COLOR: Crimson
ch.X,7ch,turn
$k=0$,sk,7scbl,$k++$,ss@R[][k++],turn
(sk,7scbl,ch,turn
sk,7scbl,$k++$,ss@R[][k++],turn
)*16
#Sewing together
DEF: ss2togA=ss1@[@+1],ss0@1[@1+1]
ss1@[-1,-2],ss0@1X,ss2togA*6

DOT: start=2
#The stocking is a bit overinflated, causing increased tension in the stitches.
#You can see that if you press 's'. The red stitches are the ones that are
#too tense. To reduce the tension in the model, uncomment the line below by
#removing the leading '#'. That does slow down the calculation a couple of times.
#DOT: inflate=1.0
`;


var textBootie = `#Baby booties showcase
COLOR: Violet
9ch,turn
sk,(hdc2inc,3hdc,3dc,dc5inc).R,turn
(dc@[0,1],2dc,3hdc,hdc2inc).R,ss@[0,-1]
ch,(2hdc2inc,6hdc,5hdc2inc,6hdc,2hdc2inc)@R~,hdc@[-1,-1],ss@[%,0] # Work last slip stitch in chain space.
ch,2hdc,hdc2inc,8hdc,2hdc2inc,2hdc,2hdc2inc,2hdc,2hdc2inc,8hdc,hdc2inc,hdc,hdc2inc,ss@[%,0]
ch,sk,41scbl,ss@[%,0]
ch,sk,41hdc,ss@[%,0]
ch,sk,10hdc,(hdc2tog,hdc)*2,4dc2tog,(hdc,hdc2tog)*2,11hdc,ss@[%,0]
ch,sk,10hdc,6dc2tog,11hdc,ss@[%,0]
ch,sk,(9sc,4dc2tog,10sc).R[],ss@[%,0]
ch.X,9ch,turn
$k=0$,sk,9scbl,ss@R[][k++],ss@R[][k++],turn
(2sk,9scbl,ch,turn
sk,9scbl,ss@R[][k++],>,ss@R[][k++],turn
)*11
#Sewing together
DEF: ss0=&ss0^:B~::B-0.5-!
DEF: ss1=&ss1^A(ss2tog):B~A-B::!-1-A;B-0.5-A
DEF: ss2tog=ss1@[@-1],ss0@1[@1-1]
ss1@[-1,-2],ss0@1X,ss2tog*8
DOT: start=1
`;

var textBlanket = `#Baby blanket showcase
DEF: dc=Copy(dc,3)
COLOR: Ivory
[7ch]*10,5ch,turn
$K=0,m=0$,3ch,dc2inc,3sk,sc,[3ch.C[m,K++],3dc,3sk,sc]*10,turn
{$m++,k=0$,3ch,dc2inc,[sc,3ch.C[m,k++],3dc]@C[m-1,K-(k)]*10,sc@[-1,2],turn
}*15
`;

var textHat = `# Hat showcase
# Design "Lady's Crochet Tam o' Shanter"
# from "Weldon's Practical Crochet, 194th Series"
# which is released in the public domain here:
# https://www.antiquepatternlibrary.org/html/warm/K-WK015-01.htm
#

5ch.Ring+1!,ss@[%,0]
9sc@Ring
sc2inc*9
[sc2inc,sc]*9
27sc
[2sc,sc2inc]*9
36sc
[5sc,sc2inc]*6
42sc
[2sc,sc2inc]*14
56sc
[7sc,sc2inc]*7
63sc
[8sc,sc2inc]*7
70sc
[4sc,sc2inc]*14
[84sc
]*4
\\Row 20:\\[2sc,sc2inc]*28
112sc
[7sc,sc2inc]*14
126sc
[2sc,sc2inc]*42
168sc
[5sc,sc2inc]*28
[6sc,sc2inc]*28
[224sc
]*3
[14sc,sc2tog]*14
[8sc,sc2tog]*21
[7sc,sc2tog]*21
[6sc,sc2tog]*21
[5sc,sc2tog]*21
[4sc,sc2tog]*21
[3sc,sc2tog]*21
#7th and 8th decrease rounds in original have a stitch count error. Skipped 8th round to avoid the issue.
[84sc
]*7
83sc,ss@[%,0]
#Ensure the hat is not overinflated. Setting this
#parameter slows down the code by a factor of two.
#The default value for inflate is infinity.
DOT: inflate=2.0
`;



var textFilet = `#Filet stitch showcase
# I used an ASCII art generator to produce the series of X's and O's below. 
# I had to reverse every other line of the output as one turns the project at the end of each row.
DEF: dc=Copy(dc,3)
DEF: O=2ch,2sk,dc
DEF: X=COLOR:Light Coral,3dc,COLOR:Linen
DEF: OX=2ch,2sk,COLOR:Light Coral,4dc,COLOR:Linen
DEF: _=3ch
# BACKGROUND:green
COLOR:Linen
ch,54_,3ch,turn
4sk,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,3ch,turn
4sk,O,O,O,O,OX,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,OX,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,OX,X,X,O,O,O,3ch,turn
4sk,O,OX,O,O,OX,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,OX,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,OX,O,O,O,O,O,3ch,turn
4sk,O,O,O,O,OX,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,OX,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,OX,O,O,3ch,turn
4sk,O,OX,O,O,O,O,O,OX,OX,X,O,O,OX,X,X,X,O,O,O,OX,X,X,X,O,O,OX,OX,X,X,O,O,O,OX,X,X,X,O,O,OX,X,X,X,O,O,O,3ch,turn
4sk,O,O,O,O,OX,O,O,OX,O,O,O,OX,O,OX,O,O,OX,X,O,OX,O,O,O,OX,O,OX,O,O,O,OX,O,O,O,OX,O,O,O,O,O,O,OX,O,O,3ch,turn
4sk,O,OX,O,O,O,O,O,O,OX,O,O,O,OX,O,O,O,OX,O,OX,O,O,O,O,O,O,OX,O,O,O,OX,O,OX,X,X,X,X,X,O,O,OX,O,O,O,O,O,3ch,turn
4sk,O,O,O,O,OX,O,O,O,O,O,O,O,OX,O,OX,O,O,O,OX,O,O,O,O,O,O,OX,O,OX,O,O,O,OX,O,O,O,OX,O,O,O,O,O,O,OX,O,O,3ch,turn
4sk,O,OX,O,O,OX,O,O,OX,O,O,O,OX,O,O,O,OX,O,OX,O,O,O,OX,O,OX,O,O,O,OX,O,OX,O,O,O,OX,O,O,OX,O,OX,O,O,3ch,turn
4sk,O,O,OX,X,O,O,O,O,OX,X,X,X,O,O,OX,O,O,O,OX,O,O,OX,X,X,X,O,O,O,OX,X,X,X,O,O,O,O,OX,O,O,O,OX,X,X,O,O,O,3ch,turn
4sk,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,3ch,turn
4sk,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,3ch,turn
4sk,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,3ch,turn
4sk,O,O,O,O,O,O,O,O,OX,X,X,X,X,O,O,OX,X,X,X,X,O,O,O,OX,X,O,O,O,O,OX,X,X,X,O,O,O,OX,X,O,O,O,O,OX,X,X,X,O,O,3ch,turn
4sk,O,OX,O,O,OX,O,O,OX,O,OX,O,O,OX,O,O,OX,O,O,OX,O,OX,O,O,O,OX,O,O,OX,O,OX,O,O,O,O,O,O,O,O,O,O,O,O,O,3ch,turn
4sk,O,O,O,O,O,O,O,O,O,O,O,O,OX,O,OX,O,O,OX,O,O,OX,O,O,O,OX,O,OX,O,O,OX,O,OX,O,O,O,OX,O,OX,O,O,OX,O,O,3ch,turn
4sk,O,OX,O,O,OX,O,OX,O,O,O,OX,O,OX,O,O,OX,O,OX,O,O,O,OX,O,O,OX,O,O,OX,O,OX,O,O,O,O,O,O,O,O,O,O,O,O,O,3ch,turn
4sk,O,O,O,O,O,O,O,O,O,OX,X,X,X,O,OX,O,O,OX,O,O,OX,O,O,O,OX,O,O,OX,X,X,X,O,OX,O,O,O,OX,O,O,OX,X,X,X,O,O,3ch,turn
4sk,O,OX,O,O,O,O,O,OX,X,X,X,X,X,O,OX,X,O,O,O,O,OX,X,X,X,X,X,O,O,OX,O,O,OX,O,OX,O,O,O,O,O,O,O,O,O,O,O,O,O,3ch,turn
4sk,O,O,O,O,O,O,O,O,O,O,O,O,OX,O,OX,O,O,OX,O,O,OX,O,O,O,OX,O,O,O,OX,OX,O,OX,O,O,O,OX,O,O,O,O,O,OX,O,O,3ch,turn
4sk,O,OX,O,O,O,O,O,OX,O,O,O,OX,O,OX,O,OX,O,O,OX,O,O,O,OX,O,O,OX,O,O,OX,O,OX,O,O,O,O,O,O,O,O,O,O,O,O,O,3ch,turn
4sk,O,O,O,O,O,O,O,O,OX,X,X,X,X,O,O,OX,X,X,X,X,O,OX,O,O,O,OX,O,OX,O,O,OX,O,OX,O,O,O,OX,O,O,O,O,O,OX,O,O,3ch,turn
4sk,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O
DOT: start=1
`;

var textFlower = `# Irish crochet showcase
# Designs adapted from "Irish Crochet Lace Book No. 132"
# which is released in the public domain here:
# https://www.antiquepatternlibrary.org/html/warm/6-TA008-02.htm
#
#Design No 8415-A
DEF: dc=Copy(dc,3)
DEF: hdc=Copy(hdc,2)
[start_a_new_chain,7ch].Ring,ss@[%,0]
$sp=0,s=0$,2ch,ch.base[0,5],3ch.chain_space[0,sp++]+!,[dc.base[0,s++]@Ring,3ch.chain_space[0,sp++]+!]*5,ss@[%,2]
$sp=0,s=0$,ch,[sc,hdc,3dc,hdc,>,sc]@chain_space[0,sp++]*6,ss@[%,0]
$s=0,sp=0$,sc.base[1,5]@base[0,5],(5ch.chain_space[1,sp++]+!,>,sc.base[1,s]@base[0,s++])*6,ss@[%,0]
$sp=0,s=0$,ch,[sc,hdc,5dc,hdc,>,sc]@chain_space[1,sp++]*6,ss@[%,0]
$sp=0,s=0$,sc@base[1,5],(7ch.chain_space[2,sp++]+!,>,sc@base[1,s++])*6,ss@[%,0]
$sp=0,s=0$,ch,[sc,hdc,7dc,hdc,>,sc]@chain_space[2,sp++]*6,ss@[%,0]
DOT: start=175

#Flower
$petal=0$,(start_a_new_chain,3ch).Petal[petal++],(3ch.Petal[petal++])*3,2ch.Petal[petal],ss.Petal[petal]@[%,0]
$c6=0$,ch,sk,[6ch.chain_space[c6++],2sk,>,sc]*5,sc@[%,0]
$c6=0$,ch,[sc,hdc,dc,8tr,dc,hdc,>,sc]@chain_space[c6++]*5,ss@[%,0],ch
$petal=0$,ss@Petal[petal],[hdc,5dc,hdc]@Petal[petal++]*5,ss@[%,0]

# Elements of design No 8422-A
# Stem
[start_a_new_chain.Beginning,28ch,ch.End],turn
@End,29sc,ch,turn
#work in back loops:
[sc@Beginning,29sc,turn
>,sc@End,29sc,turn
]*2

# Petal (added some picots)
DEF: p=3ch,ss@1[%,-4]
[start_a_new_chain,19ch].Foundation,turn
sk,18sc.Row1,sc3inc.Row1,turn
[sk,18sc.Row1,sk]@Foundation,ch
#in back loops:
$s=0$,[18sc,3sc2inc,18sc]@Row1,4ch.chain_spaceA[s++],turn
,@[-1,-1],sk@[sc:@+1],[3sk@[sc:@+1],sc,4ch.chain_spaceA[s++]]*4,[2sk@[sc:@+1],sc,4ch.chain_spaceA[s++]]*3,[3sk@[sc:@+1],sc,>,4ch.chain_spaceA[s++]]*4,turn
([2sc,p,2sc]@chain_spaceA[--s])*4,([3sc,p,2sc]@chain_spaceA[--s])*3,([2sc,p,2sc]@chain_spaceA[--s])*3,[2sc,p,2sc]@chain_spaceA[--s]~

#Control the separation between the disjoint pieces. Default is 1.5
DOT: separate=0.8
`;

var textFlower2 = `# Irish crochet flower showcase
# Design adapted from "Priscilla Irish Crochet Book, Number 1"
# which is released in the public domain here:
# https://www.antiquepatternlibrary.org/pub/PDF/6-JA034PrisIrish1.pdf
# Note: The original uses British notation as well as strands. Here I rewrote it to use American notation, and replaced the strands with chains.
# Design shown in figure 40 of the book:
DEF: p=3ch,ss@1[%,%-4]
DEF: ch=Copy(ch,1,1)
DEF: sc=Copy(sc,1,1)
6ch.Ring+1!,ss@[%,0]
[ch,15sc].Ring1[]@Ring,ss@[%,0]
ch,sk,sc,[2sc,<,p]*8,ss@[%,0],sc@Ring1[][0]
$c=0$,@Ring1[][0],[7ch.chain_space[0,c++]+!,sk,>,sc]*8,ss@[-1,-1]
$c=0$,([5sc,p,6sc,p,4sc]@chain_space[0,c++])*8,ss@[%,0]
DOT:start=4`;

var textDoily = `#Doily showcase
#"Swirls" doily pattern from "Lily Design Book No. 79 Doilies",
#which is released in the public domain here:
#https://www.antiquepatternlibrary.org/html/warm/6-TA012.htm
#Some mistakes in original were fixed.
BACKGROUND: rgb(126,8,80)
DEF: hdc=Copy(hdc,2)
DEF: dc=Copy(dc,3)
DEF: tr=Copy(tr,4)
DEF: long_tr=Copy(trtr,9)
DEF: trtr=Copy(trtr,8)
DEF: some_space=&some space^:B~::
COLOR:white
DOT:start=18
2ch,sc@[%,0],5sc@[@],ss@[sc:0,0]
$k=0$,3ch,7ch.C[k++],dc@[sc:0,1],[7ch.C[k++],dc@[sc:@+1]]*4,4ch,dc@[%,2]
$k=0,n=0$,6dc.D[n++]@[-1,2],sc@C[k++],[6dc.D[n++]@[dc:@],>,sc@C[k++]]*5,ss@[dc:-1,-1],ss@[dc:%,0]
$m=0,n=0,petal=0$,{7ch.A[m++],[8ch,ch.Petal[petal++],turn
sk,sc,hdc,dc,dc2tog,dc,hdc,ss
]*3
ss@A[m-1][0],sc,hdc,dc2tog,tr,tr2inc,turn
ss@D[n++][5],ss,>,ss
}*6
$petal=0$,start_at@Petal[petal++]
$ring=0$,{10ch,[dc,5ch,dc]@Petal[petal++],10ch,sc@Petal[petal++],3ch,>,sc@Petal[petal++]}*6,ss@[%,0],ss
$c=0$,5ch,dc@[-1,4],[2ch,2sk@[ch:@+1],dc]*3,{5ch.C5[c++],dc@[@],[2ch,2sk@[ch:@+1],dc]*4,2ch,dc@[@+4],ch,>,ch,dc@[@+4],[2ch,2sk@[ch:@+1],dc]*4}*6,sc@[%,2]
$c=0,r=0$,ch.Z0,sc.Z1@[-1,2],[2sc,sc@[dc:@]]*4,{3sc@C5[c],ch,7ch.R[r]+!0,turn
ss@1[-1,-8],ch,turn
[sc,hdc.Ring[ring++],14dc,hdc,sc]@R[r++],3sc@C5[c++],sc@[dc:@],>,[2sc,sc@[dc:@]]*10}*6,[2sc,sc@[dc:@]]*5,sc,ss@Z0,ch,sc@Z1
$c=0,ring=0$,{4ch.C4[c++]+!,long_tr@Ring[ring++],[4ch.C4[c++]+!,trtr]*13,4ch.C4[c++]+!,long_tr,4ch.C4[c++]+!,16sk@[sc:@+1],2sc@[sc:@+1],[sk,sc]*2,>,sc@[sc:@+1]}*6,ss@[-1,-1],ss@[%,0],6ss
$c=2,c1=0$,3ch,dc@[-1,7],{[4ch.C41[c1++]+!,[some_space,2dc,some_space]@C4[c++]]*13,$c++$,$c++$,>,[some_space,2dc,some_space]@C4[c++]}*6,ss@[%,2],8ss
$c1=1,c=0$,3ch,[some_space,2dc]@C41[c1++],{[4ch.C42[c++]+!,3dc@C41[c1++]]*10,$c1++$,$c1++$,>,3dc@C41[c1++]}*6,ss@[%,2],4ss
$c=1,c3=0$,3ch,dc@[-1,7],{[4ch.C43[c3++]+!,4dc@C42[c++]]*8,4ch.C43[c3++]+!,2dc@C42[c++],>,2dc@C42[c++]}*6,ss@[%,2],3ss
DEF: p=5ch,ss@1[%,-5]
$c3=1,c=0$,4ch,3ch.Z2,p,[5ch.Z2,3ch].C8[c++]+!,p,3ch,tr@C43[c3++],[3ch,p,8ch.C8[c++]+!,p,3ch,tr@C43[c3++]]*7,{tr@C43[c3++],[3ch,p,8ch.C8[c++]+!,p,3ch,tr@C43[c3++]]*8}*5,ss@[%,3],8ss@Z2
$c3=1,c=0$,4ch,3ch.Z3,p,[5ch.Z3,3ch].C81[c++]+!,p,3ch,tr@C8[c3++],[3ch,p,8ch.C81[c++]+!,p,3ch,tr@C8[c3++]]*6,{tr@C8[c3++],[3ch,p,8ch.C81[c++]+!,p,3ch,tr@C8[c3++]]*7}*5,ss@[%,3],8ss@Z3
$c3=1,c=0$,4ch,4ch.Z4,p,[[4ch,ch.C9[c++]].Z4,4ch],p,4ch,tr@C81[c3++],[4ch,p,4ch,ch.C9[c++],4ch,p,4ch,tr@C81[c3++]]*5,{tr@C81[c3++],[4ch,p,4ch,ch.C9[c++],4ch,p,4ch,tr@C81[c3++]]*6}*5,ss@[%,3],9ss@Z4
$c=0,c5=0,c9=0$,4ch,ch.Z5,5ch.C51[c5++]+!,tr@C9[c++],[9ch.C91[c9++],[tr,5ch.C51[c5++]+!,tr]@C9[c++]]*35,4ch,tr.Z6@Z5
$c=0,c9=0,c5=0$,{([ch.Ch[c++]+!,tr]*8)@C51[c5++],ch.Ch[c++]+!,>,sc@C91[c9++][4]}*36,sc.Z7@Z6
$c=0,c7=0,c8=0$,{sc@Ch[c++],(2sc@Ch[c++])*5,4ch.C10b[c7]+!,6ch.C10a[c7++]+!,turn
@[-1,-1],ss@[sc:@+6],ch,turn
8sc@C10a[c7-1]~,8ch.C82[c8++]+!,turn
@[-1,-1],ss@[sc:@+4],ch,turn
[5sc,5ch,ss@1[%,-6],5sc,ss]@C82[c8-1]~,ch,[4sc,ss]@C10b[c7-1]~,ch,[2sc@Ch[c++]]*2,sc@Ch[c++]}*36,ss@Z7
`;

var textSnowman = `#Simple amigurumi showcase
COLOR:white
ring.R
5sc@R
sc2inc*4,sc3inc
[sc2inc,>,sc]*6
[2sc,sc2inc,>,3sc,sc2inc]*3
sc2inc, 3sc, sc2inc, 4sc, sc2inc, 3sc, sc2inc, 4sc, sc2inc, 3sc
2sc, sc2inc, 4sc, sc2inc, 5sc, sc2inc, 4sc, sc2inc, 5sc, sc2inc, 2sc
3sc, sc2inc, 7sc, sc2inc, 7sc, sc2inc, 7sc, sc2inc, 4sc
5sc, sc2inc, 11sc, sc2inc, 11sc, sc2inc, 6sc
10sc, sc2inc, 12sc, sc2inc, 12sc, sc2inc, 2sc
2sc, sc2inc, 13sc, sc2inc, 13sc, sc2inc, 11sc
19sc, sc2inc, 21sc, sc2inc, 3sc
18sc, sc2inc, 28sc
48sc
48sc
41sc, sc2tog, 5sc
8sc, sc2tog, 22sc, sc2tog, 13sc
1sc, sc2tog, 13sc, sc2tog, 13sc, sc2tog, 12sc
8sc, sc2tog, 12sc, sc2tog, 12sc, sc2tog, 4sc
3sc, sc2tog, 11sc, sc2tog, 11sc, sc2tog, 8sc
7sc, sc2tog, 7 sc, sc2tog, 7 sc, sc2tog, 7sc, sc2tog
2sc, sc2tog, 5 sc, sc2tog, 4 sc, sc2tog, 5sc, sc2tog, 4sc, sc2tog, 2sc
sc2tog, 3sc, sc2tog, 4sc, sc2tog, 3sc, sc2tog, 4sc, sc2tog, 3sc
sc2tog, 2sc, sc2tog, 2sc, sc2tog, 3sc, sc2tog, 2sc, sc2tog, 3sc
sc2tog, sc, sc2tog, sc, sc2tog, sc, sc2tog, sc2tog, sc, sc2tog, sc
sc2tog, sc2tog, sc3tog, sc2tog, sc2tog
sc5tog
start_anew
ring.R2
5sc@R2
sc2inc, sc2inc, sc2inc, sc2inc, sc3inc
sc2inc, sc, sc2inc, sc, sc2inc, sc, sc2inc, sc, sc2inc, sc, sc2inc
2sc, sc2inc, 4sc, sc2inc, 3sc, sc2inc, 3sc, sc2inc, sc
sc2inc, 4sc, sc2inc, 5sc, sc2inc, 4sc, sc2inc, 4sc
2sc, sc2inc, 5sc, sc2inc, 6sc, sc2inc, 5sc, sc2inc, 3sc
sc, sc2inc, 13sc, sc2inc, 13sc
sc2inc, 30sc
32sc
15sc, sc2tog, 15sc
8sc, sc2tog, 13sc, sc2tog, 6sc
sc2tog, 6sc, sc2tog, 5sc, sc2tog, 5sc, sc2tog, 5sc
3sc, sc2tog, 5sc, sc2tog, 4sc, sc2tog, 4sc, sc2tog, 1sc
sc, sc2tog, 3sc, sc2tog, 4sc, sc2tog, 3sc, sc2tog, 2sc
sc, sc2tog, sc, sc2tog, sc, sc2tog, sc2tog, sc, sc2tog, sc, sc2tog
sc2tog, sc2tog, sc3tog, sc2tog, sc2tog
sc5tog
start_anew
ring.R1
5sc@R1
sc2inc, sc2inc, sc2inc, sc2inc, sc3inc
sc2inc, 2sc, sc2inc, 2sc, sc2inc, 2sc, sc2inc, sc
3sc, sc2inc, 4sc, sc2inc, 4sc, sc2inc, sc
7sc, sc2inc, 8sc, sc2inc, sc
20sc
3sc, sc2tog, 8sc, sc2tog, 5sc
4sc, sc2tog, 4sc, sc2tog, 4sc, COLOR:black,sc2tog,COLOR:white
sc, COLOR:black,sc2tog,COLOR:white, 2sc, sc2tog, 2sc, sc2tog, 2sc, sc2tog
sc2tog, sc3tog, sc2tog, sc2tog, sc2tog
COLOR:orange
5sc
sc2tog,sc,sc2tog
3sc
sc2tog,sc
#Sewing:
# The coortinates of these nodes/stitches are chosen 
# to place/sew together the spheres on top of each other. 
# I found the node names by first running the model without 
# the lines below. Then I hovered over the nodes on a main 
# diagonal of each sphere and wrote them down below. The coordinates
# are along the x-axis. I picked them by knowing the circumference
# of each spheres (given by the largest number of stitches). 
DOT: "0,0|0" {-19,0,0}
DOT: "26,0|748" {0,0,0}
DOT: "28,0|750" {0,0,0}
DOT: "45,0|1066" {12,0,0}
DOT: "53,9|1132" {12,0,0}
DOT: "53,0|1123" {19,0,0}
DOT: start=1
# Prevent repulsion between the disjoint balls, which would normally
# separate the spheres apart.
DOT: separate=0
# When nodes are fixed in position as above, the code needs a lot
# more iterations to converge well.
DOT: iterations=4000
`;
//start_anew: '&start_anew^A(hidden):~::!-skip-A',
var Dictionary = {
    ring: '&ring^A(ring):~::!-0.1-A',
    tie_up: '&tie up stitches^A(tie):B~A-B::!-0.1-A;B-0.7-A',
    start_at: '&start_at^A(hidden):B~A-B::!-skip-A;A-0.001-B',
    start_anew: '&start_anew^A(hidden):~::!-skip-A',
    start_a_new_chain: '&start a new chain^A(ch):~::!-skip-A',
    sk: '&sk^:A~::',
    ch: '&ch^A(ch):~::!-1-A',
    ss: '&ss^A(ss):B~A-B::!-1-A;B-0.4-A',
    sc: '&sc^A(sc):B~A-B::!-1-A;B-1-A',
    hdc: '&hdc^A(hdc):B~A-B::!-1-A;B-1.5-A',
    dc: '&dc^A(dc):B~A-B::!-1-A;B-2-A',
    bpdc: '&bpdc^A(bpdc):B~A-B::!-1-A;B-1.5-A',
    fpdc: '&fpdc^A(fpdc):B~A-B::!-1-A;B-1.5-A',
    tr: '&tr^A(tr):B~A-B::!-1-A;B-2.5-A',
    dtr: '&dtr^A(dtr):B~A-B::!-1-A;B-3-A',
    trtr: '&trtr^A(trtr):B~A-B::!-1-A;B-3.5-A',
    sc3bobble: '&a sc bobble of 3 stitches^A(sc):B~A-B:C;D;E;F;G;H:!-1-A;B-0.4-C;C-0.4-D;D-0.4-A;B-0.4-E;E-0.4-F;F-0.4-A;B-0.4-G;G-0.4-H;H-0.4-A',
    dc3bobble: '&a dc bobble of 3 stitches^A(dc):B~A-B:C;D;E;F;G;H:!-1-A;B-0.7-C;C-0.8-D;D-0.7-A;B-0.7-E;E-0.8-F;F-0.7-A;B-0.7-G;G-0.8-H;H-0.7-A',
    dc4bobble: '&a dc bobble of 4 stitches^A(dc):B~A-B:C;D;E;F;G;H;I;J:!-1-A;B-0.7-C;C-0.8-D;D-0.7-A;B-0.7-E;E-0.8-F;F-0.7-A;B-0.7-G;G-0.8-H;H-0.7-A;B-0.7-I;I-0.8-J;J-0.7-A',
    dc5bobble: '&a dc bobble of 5 stitches^A(dc):B~A-B:C;D;E;F;G;H;I;J;K;L:!-1-A;B-0.7-C;C-0.8-D;D-0.7-A;B-0.7-E;E-0.8-F;F-0.7-A;B-0.7-G;G-0.8-H;H-0.7-A;B-0.7-I;I-0.8-J;J-0.7-A;B-0.7-K;K-0.8-L;L-0.7-A',
    tr4bobble: '&a tr bobble of 4 stitches^A(dc):B~A-B:C;D;E;F;G;H;I;J:!-1-A;B-1.2-C;C-0.8-D;D-1.2-A;B-1.2-E;E-1.2-F;F-1.2-A;B-1.2-G;G-1.2-H;H-1.2-A;B-1.2-I;I-1.2-J;J-1.2-A',
    dc3pc: '&dc3pc^A(dc3pc):B~A-B:C;D(dc);E;F(dc);G;H(dc):!-1-A;B-1.2-C;C-1.2-D;B-1-E;E-1-F;B-1.2-G;G-1.2-H;!-0.8-D;D-0.8-F;F-0.8-H;!-0.33-D;D-0.33-H;H-0.33-A',
    dc4pc: '&dc4pc^A(dc4pc):B~A-B:C;D(dc);E;F(dc);G;H(dc);I;J(dc):!-1-A;B-1.2-C;C-1.2-D;B-1-E;E-1-F;B-1.2-G;G-1.2-H;B-1.2-I;I-1.2-J;!-0.8-D;D-0.8-F;F-0.8-H;H-0.8-J;!-0.33-D;D-0.33-J;J-0.33-A',
    dc5pc: '&dc5pc^A(dc5pc):B~A-B:C;D(dc);E;F(dc);G;H(dc);I;J(dc);K;L(dc):!-1-A;B-1.2-C;C-1.2-D;B-1-E;E-1-F;B-1.2-G;G-1.2-H;B-1.2-I;I-1.2-J;B-1.2-K;K-1.2-L;!-0.8-D;D-0.8-F;F-0.8-H;H-0.8-J;J-0.8-L;!-0.33-D;D-0.33-L;L-0.33-A',
    picot3: '&picot^A(ch);B(ch);C(ch);D(ss):~::!-1-A;A-1-B;B-1-C;C-1-D;!-0.4-D',
    scbl: '&scbl^A(scbl):B[back]~A-B::!-1-A;B-1-A',
    ssbl: '&ssbl^A(ssbl):B[back]~A-B::!-1-A;B-0.4-A',
    dcbl: '&dcbl^A(dcbl):B[back]~A-B::!-1-A;B-2-A',
    hdcbl: '&hdcbl^A(hdcbl):B[back]~A-B::!-1-A;B-1.5-A',
    trbl: '&trbl^A(trbl):B[back]~A-B::!-1-A;B-2.5-A',
    dtrbl: '&dtrbl^A(dtrbl):B[back]~A-B::!-1-A;B-3-A',
    trtrbl: '&trtrbl^A(trtrbl):B[back]~A-B::!-1-A;B-3.5-A',
    scfl: '&scfl^A(scfl):B[front]~A-B::!-1-A;B-1-A',
    ssfl: '&ssfl^A(ssfl):B[front]~A-B::!-1-A;B-0.4-A',
    dcfl: '&dcfl^A(dcfl):B[front]~A-B::!-1-A;B-2-A',
    hdcfl: '&hdcfl^A(hdcfl):B[front]~A-B::!-1-A;B-1.5-A',
    trfl: '&trfl^A(trfl):B[front]~A-B::!-1-A;B-2.5-A',
    dtrfl: '&dtrfl^A(dtrfl):B[front]~A-B::!-1-A;B-3-A',
    trtrfl: '&trtrfl^A(trtrfl):B[front]~A-B::!-1-A;B-3.5-A'
};

var OriginalDictionary = JSON.parse(JSON.stringify(Dictionary));

var DEBUG = '';
var STATS = {};
var STATSstretch = '';

function findPosNodes(str) {
    const regex = /(?<=\^)[A-Z]/g;
    const matches = str.match(regex);
    return matches ? matches : [];
}

function findAttachmentNodes(str) {
    const regex = /(?<=\-\d*)[A-Z]/g;
    const matches = str.match(regex);
    return matches ? matches : [];
}

function findUniqueCapitalLetters(str) {
    const uniqueLetters = new Set();
    let caps = str.match(/([A-Z])/g);
    if (caps == null)
        return [];
    for (let i of caps) {
        uniqueLetters.add(i);
    }
    return Array.from(uniqueLetters);
}

//&type^topNodes(type)_bottomNodes~attachments:hiddenNodes:connections

//{
//    topNodesNames: ['A'],
//    topNodes: {
//        A: {
//            type: 'cl3',
//            attach: 'B'
//        }
//    },
//    bottomNodesNames: ['B'],
//    bottomNodes: {
//        B: {
//            attach_depth: 1
//        }
//    },
//    otherNodes: {
//        C: {
//            type: 'hidden'
//        },
//        D: {
//            type: 'hidden'
//        },
//        E: {
//            type: 'hidden'
//        },
//        F: {
//            type: 'hidden'
//        },
//        G: {
//            type: 'hidden'
//        },
//        H: {
//            type: 'hidden'
//        }
//    },
//    connections: {
//        '!-A': 1,
//        'B-D': 1 / 3,
//        'D-C': 1 / 3,
//        'C-A': 1 / 3,
//        'B-F': 1 / 3,
//        'F-E': 1 / 3,
//        'E-A': 1 / 3,
//        'B-H': 1 / 3,
//        'H-G': 1 / 3,
//        'G-A': 1 / 3,
//    }
//};
//{
//    topNodesNames: ['A'], // order
//    topNodes: {
//        A: {
//            type: 'cl3',
//            attach: 'B'
//        }
//    },
//    bottomNodesNames: ['B'], //order
//    bottomNodes: {
//        B: {
//            attach_depth: 1
//        }
//    },
//    otherNodes: {
//        C: {
//            type: 'hidden'
//        }
//    },
//    connections: {
//        '!A': len
//    }
//};



function handle_changeHeightWidth(stitch, new_Type, H, W) {
    if (stitch[0] !== '&')
        throw new Error('Stitch code needs to start with &: ' + stitch);
    var [Type, Top, bottom, attachments, hidden, cons] = stitch.slice(1).split(/[\^\:_~]/g);

    if (hidden.trim().length > 0)
        throw new Error('Do not know how to change width/height of stitches with internal nodes: ' + stitch);

    const regex1 = /([A-Z0-9a-z_]+)\(([^\);]*)\)/g;
    let match;

    var nameTop = [];
    while (match = regex1.exec(Top)) {
        nameTop.push(match[1]);
    }

    const regex = /(\d+)?([A-Za-z_0-9]+)/g;
    var nameBottom = [];
    while (match = regex.exec(bottom)) {
        const name = match[2];
        nameBottom.push(name);
    }
    var resetW = false;
    var resetH = false;
    if (H < 0)
        resetH = true;
    if (W < 0)
        resetW = true;
    var Cons = '';
    for (var con of cons.split(';')) {
        if (con.trim().length > 0) {
            let [n0, len, n1] = con.split('-');

            let star = '';
            if (n0[0] === '*') {
                star = '*';
                n0 = n0.slice(1);
            }
            let top0 = ((n0 === '!') || (nameTop.includes(n0)));
            let top1 = ((n1 === '!') || (nameTop.includes(n1)));
            let bottom0 = nameBottom.includes(n0);
            let bottom1 = nameBottom.includes(n1);
            if (resetH)
                H = len;
            if (resetW)
                W = len;
            if (top0 && bottom1)
                Cons += star + n0 + '-' + H + '-' + n1 + ';';
            else if (top1 && bottom0)
                Cons += star + n0 + '-' + H + '-' + n1 + ';';
            else if (top0 && top1)
                Cons += star + n0 + '-' + W + '-' + n1 + ';';
            else
                Cons += star + n0 + '-' + len + '-' + n1 + ';';

        }
    }
    Cons = Cons.slice(0, -1);


    return '&' + new_Type + '^' + Top.replace(new RegExp('\\b' + Type + '\\b', 'g'), new_Type) + ':' + bottom + '~' + attachments + '::' + Cons;
}

function handle_Ninc(stitch, N) {
    if (stitch[0] !== '&')
        throw new Error('Stitch code needs to start with &: ' + stitch);
    var [Type, Top, bottom, attachments, hidden, cons] = stitch.slice(1).split(/[\^\:_~]/g);

    const regex1 = /([A-Z0-9a-z_]+)\(([^\);]*)\)/g;
    let match;


    var lastNameTop = '';
    var TopNew = '';
    for (var kb = 0; kb < N; kb++)
        while (match = regex1.exec(Top)) {
            TopNew += match[1] + String(kb) + '(' + match[2] + ');';
            lastNameTop = match[1];
        }
    TopNew = TopNew.slice(0, -1);

    const regex = /(\d+)?([A-Za-z_0-9]+)/g;
    var nameBottom;
    var Bottom = '';
    var k = 0;
    while (match = regex.exec(bottom)) {
        const name = match[2];
        var number = match[1];
        nameBottom = name;
        if (!number)
            number = '';
        Bottom += number + name;
        if (k > 0)
            throw new Error('Cannot handle Ninc for stitches with more than one bottom node. Try to specify stitch dictionary entry instead for ' + stitch + String(N) + 'inc');
        k++;
    }



    const regexH = /([A-Z0-9a-z_]+)\(?([^;\)]*)\)?/g;
    var Hidden = '';
    for (var kH = 0; kH < N; kH++)
        while (match = regexH.exec(hidden)) {
            let type = match[2];
            if (type.trim().length == 0)
                type = 'hidden';
            Hidden += match[1] + String(kH) + '(' + type + ');';
        }
    Hidden = Hidden.slice(0, -1);


    var Cons = '';
    for (var kC = 0; kC < N; kC++)
        for (var con of cons.split(';')) {
            if (con.trim().length > 0) {
                let [n0, len, n1] = con.split('-');
                let star = '';
                if (n0[0] === '*') {
                    star = '*';
                    n0 = n0.slice(1);
                }
                if ((n0 !== nameBottom) && (n0 !== '!'))
                    n0 += String(kC);
                if ((n1 !== nameBottom) && (n1 !== '!'))
                    n1 += String(kC);
                if ((n0 === '!') && (kC > 0))
                    n0 = lastNameTop + String(kC - 1);
                if ((n1 === '!') && (kC > 0))
                    n1 = lastNameTop + String(kC - 1);

                Cons += star + n0 + '-' + len + '-' + n1 + ';';

            }
        }
    Cons = Cons.slice(0, -1);

    var Attachments = '';
    for (var kA = 0; kA < N; kA++)
        if (attachments.trim() !== '')
            for (var a of attachments.split(';')) {
                a = a.split('-');
                Attachments += a[0] + String(kA) + '-' + a[1] + ';';
            }
    Attachments = Attachments.slice(0, -1);
    return '&' + Type + String(N) + 'inc^' + TopNew + ':' + Bottom + '~' + Attachments + ':' + Hidden + ':' + Cons;
}

function handle_Ntog(stitch, N) {
    if (stitch[0] !== '&')
        throw new Error('Stitch code needs to start with &: ' + stitch);
    var [Type, Top, bottom, attachments, hidden, cons] = stitch.slice(1).split(/[\^\:_~]/g);

    const regex1 = /([A-Z0-9a-z_]+)\(([^\);]*)\)/g;
    let match;

    var k = 0;
    var nameTop;
    var TopNew = '';
    while (match = regex1.exec(Top)) {
        nameTop = match[1];
        TopNew = match[1] + '(' + match[2] + ')';
        //TopNew = match[1] + '(' + match[2] + String(N) + 'tog' + ')'
        if (k > 0)
            throw new Error('Cannot handle Ntog for stitches with more than one top node. Try to specify stitch dictionary entry instead for ' + stitch + String(N) + 'tog');
        k++;
    }

    const regex = /(\d+)?([A-Za-z_0-9]+)/g;
    var Bottom = '';
    for (var kb = 0; kb < N; kb++)
        while (match = regex.exec(bottom)) {
            const name = match[2];
            var number = match[1];
            if (!number)
                number = '';
            Bottom += number + name + String(kb) + ';';
        }
    Bottom = Bottom.slice(0, -1);


    const regexH = /([A-Z0-9a-z_]+)\(?([^;\)]*)\)?/g;
    var Hidden = '';
    for (var kH = 0; kH < N; kH++)
        while (match = regexH.exec(hidden)) {
            let type = match[2];
            if (type.trim().length == 0)
                type = 'hidden';
            Hidden += match[1] + String(kH) + '(' + type + ');';
        }
    Hidden = Hidden.slice(0, -1);


    var Cons = '';
    for (var kC = 0; kC < N; kC++)
        for (var con of cons.split(';')) {
            if (con.trim().length > 0) {
                let [n0, len, n1] = con.split('-');

                let star = '';
                if (n0[0] === '*') {
                    star = '*';
                    n0 = n0.slice(1);
                }
                if ((n0 !== nameTop) && (n0 !== '!'))
                    n0 += String(kC);
                if ((n1 !== nameTop) && (n1 !== '!'))
                    n1 += String(kC);

                Cons += star + n0 + '-' + len + '-' + n1 + ';';



            }
        }
    Cons = Cons.slice(0, -1);

    var Attachments = '';
    if (attachments.trim() !== '')
        for (var a of attachments.split(';')) {
            a = a.split('-');
            Attachments = a[0] + '-' + a[1] + String(N - 1);
        }
    return '&' + Type + String(N) + 'tog^' + TopNew + ':' + Bottom + '~' + Attachments + ':' + Hidden + ':' + Cons;
}

function find_stitchID_by_pos(Stitches, row, pos, relative_id = -1, direction = 1, type = '') {
    var ids;
    if (type === '')
        ids = Stitches.filter(structure => {
            return structure.id.length > 0 && structure.nrow == row;
        }).map(obj => obj.id).flat(Infinity);
    else
        ids = Stitches.filter(structure => {
            return structure.id.length > 0 && structure.nrow == row;
        }).map(structure => {
            const matchingIds = Object.keys(structure.topNodes).filter(key => structure.topNodes[key].type === type).map(key => structure.topNodes[key].id);
            return matchingIds;
        }).flat(Infinity);


    if (ids.length == 0)
        throw new Error('Stitch at that position not found: [row,pos,type]=' + row + ',' + pos + ',' + type);

    //console.log(ids, pos)
    if ((relative_id) != -1 && type !== '') {
        let [s, i] = find_stitch_by_id(Stitches, relative_id);
        if (s.topNodes[s.topNodesNames[i]].type !== type) {
            //@[sc: @] and @[sc: @ + 1] should both give the first encounter of sc in this case.
            if (pos > 0)
                pos -= 1;
        }
    }

    if (direction == -1)
        ids.reverse();

    function findIndexOfElementThatIsGreaterOrEqToNIfDirectionIsPositiveAndLessOrEqIfDirectionIsNegative(arr, N, direction) {
        if (direction < 0) {
            arr = arr.map(s => -s);
            //arr.reverse() already reversed
            N = -N;
        }
        let low = 0;
        let high = arr.length - 1;
        let result = -1;

        while (low <= high) {
            let mid = Math.floor((low + high) / 2);

            if (arr[mid] === N) {
                return mid; // N is found in the array
            } else if (arr[mid] < N) {
                low = mid + 1;
            } else {
                result = mid; // Update the result to the current index
                high = mid - 1;
            }
        }

        return result;
    }

    //console.log(ids, pos, ids[pos], relative_id, findIndexOfElementThatIsGreaterOrEqToNIfDirectionIsPositiveAndLessOrEqIfDirectionIsNegative(ids, relative_id, direction), direction)
    if (relative_id != -1)
        pos = pos + findIndexOfElementThatIsGreaterOrEqToNIfDirectionIsPositiveAndLessOrEqIfDirectionIsNegative(ids, relative_id, direction);
    //console.log(ids, pos, ids[pos], relative_id)
    if ((type !== '') && (pos < 0) && (relative_id != -1))
        pos = 0;
    //console.log('debug: ', Stitches, row, pos, relative_id, direction, type, ids)
    if (!Number.isInteger(ids.slice(pos)[0]))
        throw new Error('Stitch at that position not found: [row,pos,relative_id,type]=' + row + ',' + pos + ',' + relative_id + ',' + type + '; ', Stitches);
    return ids.slice(pos)[0];
}

function find_stitch_by_id(Stitches, id) {
    var s = Stitches.filter(structure => {
        return structure.id.includes(id);
    });

    if (s.length == 1) {
        var index = s[0].id.indexOf(id);
        return [s[0], index];
    }
    if (s.length == 0)
        throw new Error('ID not found: ' + id);
    if (s.length > 1)
        throw new Error('Duplicate IDs: ' + id);
}

function last_element(arr) {
    return arr.slice(-1)[0];
}

function count_stitches(Stitches) {
    var k = 0;
    for (var s of Stitches) {
        k += s.id.length;
    }
    return k;
}

function count_stitches_in_row(Stitches, row) {
    var s = Stitches.filter(structure => {
        return (structure.nrow == row) && (structure.id.length > 0);
    });
    if (s.length == 0) {
        return [0, -1, -1];
    }

    //return last_element(last_element(s).id) - s[0].id[0]
    return [count_stitches(s), s[0].id[0], last_element(last_element(s).id)];
}


function find_label(Stitches, label) {
    var label0 = label;
    if (label.split(';').length > 1)
        label = (label.split(';')[0]).trim() + ']';
    label = label.split('!')[0];
    label = label.split('~')[0];
    label = label.split('+')[0];
    label = label.split('^')[0];
    var s = Stitches.filter(structure => {
        let g = [...structure.label].map(l => l.split('!')[0].split('+')[0].split('^')[0]);
        //console.log(label, g, structure.label)
        return (g.includes(label)) && (structure.id.length > 0);
    });
    if (count_stitches(s) == 0)
        throw new Error('Label not found: ' + label);
    return {
        'attach_id': last_element(last_element(s).id),
        'attach_ref': label0,
        'n': count_stitches(s)
    };
}

function find_label_ALL(Stitches, label) {
    if (label.split(';').length > 1)
        label = ((label.split(';')[0]).trim() + ']');
    label = label.split('!')[0];
    label = label.split('~')[0];
    label = label.split('+')[0].split('^')[0];

    var s = Stitches.filter(structure => {
        let g = [...structure.label].map(l => l.split('!')[0].split('+')[0].split('^')[0]);
        return (g.includes(label)) && (structure.id.length > 0);
    });
    if (count_stitches(s) == 0)
        throw new Error('Label not found: ' + label);
    return s;
}

function find_repeated_labels(Stitches) {
    var labels = {};
    for (var s of Stitches) {
        if (Array.isArray(s.label) && s.label.length > 0) {
            for (var label of s.label) {
                let label1 = label.split('!')[0];
                label1 = label1.split('+')[0].split('^')[0];
                if (!(label1 in labels)) {
                    let ls = find_label_ALL(Stitches, label1).map(obj => obj.id).flat(Infinity);
                    if (ls.length > 1 || label.includes('+') || label.includes('^'))
                        labels[label1] = {
                            label_ids: ls,
                            raw_label: label
                        };
                }
            }
        }
    }
    return labels;
}

function find_and_fix_references_in_repeated_labels(Stitches, turns) {
    var rep_labels = find_repeated_labels(Stitches);
    //find all stitches that attach to repeated labels.
    var REV = {};
    for (var si = 0; si < Stitches.length; si++) {
        var s = Stitches[si];
        if (typeof(s.attach_ref) === 'string' && s.attach_ref.length > 0 && s.id_attach.length > 0) {
            let label = s.attach_ref;
            let label1 = label;
            let num = 0;
            if (label1.split(';').length > 1) {
                label1 = (label1.split(';')[0]).trim() + ']';
                num = parseInt(label.split(';')[1], 10);
            }
            label1 = label1.split('!')[0];
            let rev = false;
            if (label.includes('~'))
                rev = true;
            label1 = label1.split('~')[0];
            label1 = label1.split('+')[0].split('^')[0];
            if (label1 in rep_labels) {
                if (!('attached' in rep_labels[label1]))
                    rep_labels[label1]['attached'] = {};
                if (!(String(num) in rep_labels[label1]['attached']))
                    rep_labels[label1]['attached'][num] = [si];
                else
                    rep_labels[label1]['attached'][num].push(si);
                if (!(label1 in REV))
                    REV[label1] = {};
                REV[label1][num] = rev;

                //rep_labels[label1]['attached'][num] = rep_labels[label1]['attached'][num].flat()
            }
        }
    }

    //Collect all stitch groups (such as @A[2;i]) into one.
    //console.log(REV)
    for (let k of Object.keys(rep_labels)) {
        let inds = [];
        if ('attached' in rep_labels[k]) {
            for (let i of Object.keys(rep_labels[k]['attached']).map(a => parseInt(a, 10)).sort((a, b) => a - b).map(a => String(a))) { //sort numerically
                if (REV[k][i])
                    inds.push(rep_labels[k]['attached'][i].reverse());
                else
                    inds.push(rep_labels[k]['attached'][i]);
            }
        }
        inds = inds.flat(Infinity);
        delete rep_labels[k].attached;
        rep_labels[k]['ref_inds'] = inds;
        if (inds.length == 0)
            delete rep_labels[k];
    }

    DEBUG += '=======Stitches that attach to multi-stitch labels:=======\n' + JSON.stringify(rep_labels) + '\n';

    for (let k of Object.keys(rep_labels)) {
        var c = rep_labels[k];
        //console.log('HA: ', Stitches, rep_labels, c['ref_inds'], Stitches[c['ref_inds'][0]])
        var n1 = Stitches[c['ref_inds'][0]].nrow;
        var n0 = find_stitch_by_id(Stitches, c['label_ids'][0])[0].nrow;
        var turn = 0;

        var L = 0;
        for (var r of c['ref_inds']) {
            L += Stitches[r].bottomNodesNames.length;
        }

        var SP_offset = 0;
        var Psp = [...c['label_ids']];

        if (c.raw_label.includes('+')) {
            let S = parseInt(c.raw_label.split('+')[1], 10);
            if (Number.isNaN(S))
                Psp = [c['label_ids'][0] - 1, ...c['label_ids'], last_element(c['label_ids']) + 1];
            else if (S == 0)
                Psp = [c['label_ids'][0] - 1, ...c['label_ids']];
            else if (S == 1)
                Psp = [...c['label_ids'], last_element(c['label_ids']) + 1];
            else
                throw new Error('Integer after "+" operator in label should be none, 0 or 1: ' + JSON.stringify(c));
        }
        var CarrotNum = -2;
        if (c.raw_label.includes('^')) {
            if (c.raw_label.includes('+'))
                throw new Error('Cannot combine "^" and "+" operators in label: ' + JSON.stringify(c));
            if (Psp.length != 1)
                throw new Error('Cannot use "^" operator in multi-stitch labels: ' + JSON.stringify(c));
            //Psp = [-1, ...Psp]
            CarrotNum = parseInt(c.raw_label.split('^')[1], 10);
            if (Number.isNaN(CarrotNum))
                CarrotNum = -1;
        }
        var partialSkip = false;
        if (c.raw_label.split('!').length == 2) {
            let S = parseInt(c.raw_label.split('!')[1], 10);
            if (Number.isNaN(S)) {
                L += 2;
                SP_offset = 1;
            } else if (S == 0 || S == 1) {
                partialSkip = true;
                L += 1;
                SP_offset = 1 - S; // !0 means skip first stitch, !1 means skip last; ! means skip both;;
            } else throw new Error('Syntax error after "!" in: ' + JSON.stringify(c));
        } else if (c.raw_label.split('!').length > 2)
            throw new Error('Syntax error after "!" in: ' + JSON.stringify(c));

        var Lsp = Psp.length;

        turn = sum(turns.slice(n0, n1)) % 2;
        var not_done = true;

        if (CarrotNum != -2) { //Attaching to the post of a stitch
            Lsp = 2;


            let [s0, ind1] = find_stitch_by_id(Stitches, Psp[0]);
            //  console.log('A', s0, ind1, s0.topNodesNames)
            let top_attach_node = s0.topNodesNames[ind1];
            let attach_names = [];
            for (let c of Object.keys(s0.connections).sort()) { //Make list of all connections in the stitch.
                let n0 = c.split('--')[0];
                n0 = n0[0] === '*' ? n0.slice(1) : n0;
                if (c.split('--')[1] == top_attach_node && (!s0.topNodesNames.includes(n0) && n0 !== '!'))
                    attach_names.push([n0, s0.connections[c], c]);
            }
            let [bottom_attach_node, d, con] = attach_names.slice(CarrotNum)[0]; //extract the CarrotNum connection;;
            if (s0.bottomNodesNames.includes(bottom_attach_node)) { //If bottom of connection is a bottom node, then we can use the rest of the algorithm to do the calculation; so leave not_done=true
                Psp = [s0.bottomNodes[bottom_attach_node].id, ...Psp];
            } else { //if bottom of post to which we are attaching is an "other node"
                Psp = ['^' + String(Psp[0]) + '-' + bottom_attach_node, ...Psp];
                not_done = false;
                if (Lsp == L) { //If exactly two stitches attach to the post, and the ends are not skipped; then no interpolation nodes need to be created.
                    let i = 0;
                    for (let r of c['ref_inds']) {
                        for (let b of Stitches[r].bottomNodesNames) {
                            if (turn == 0)
                                Stitches[r].bottomNodes[b].id = Psp[i + SP_offset];
                            else {
                                if (partialSkip)
                                    SP_offset = 1 - SP_offset;
                                Stitches[r].bottomNodes[b].id = Psp[Lsp - (i) - (SP_offset) - 1];
                            }
                            i++;
                        }
                        Stitches[r].id_attach = Stitches[r].bottomNodesNames.map(b => Stitches[r].bottomNodes[b].id);
                    }
                } else { //Create interpolation nodes

                    if (turn == 1) {
                        Psp.reverse();
                        if (partialSkip)
                            SP_offset = 1 - SP_offset;
                    }
                    let i = 0;
                    for (let r of c['ref_inds']) {
                        var originalBottomNodesNames = [...Stitches[r].bottomNodesNames];
                        for (let b of originalBottomNodesNames) {
                            if (L > 1)
                                isp = (i + SP_offset) * (Lsp - 1) / (L - 1);
                            else
                                isp = (0.5) * (Lsp - 1);

                            i0 = Math.floor(isp);
                            i1 = Math.ceil(isp);

                            if (i0 == i1) {
                                Stitches[r].bottomNodes[b].id = Psp[i0];
                            } else {
                                var p0 = Psp[i0];
                                var p1 = Psp[i1];
                                Stitches[r].bottomNodes[b].id = '$' + p0 + '--' + p1 + ':' + String(d * (isp - i0)) + ':' + String(d * (i1 - isp));
                            }
                            i++;
                        }
                        Stitches[r].id_attach = Stitches[r].bottomNodesNames.map(b => Stitches[r].bottomNodes[b].id);
                    }
                    ///FIXME end

                }
            }
        }

        if ((Lsp == L) && (not_done)) {
            let i = 0;
            for (let r of c['ref_inds']) {
                for (let b of Stitches[r].bottomNodesNames) {
                    if (turn == 0)
                        Stitches[r].bottomNodes[b].id = Psp[i + SP_offset];
                    else {
                        if (partialSkip)
                            SP_offset = 1 - SP_offset;
                        Stitches[r].bottomNodes[b].id = Psp[Lsp - (i) - (SP_offset) - 1];
                    }

                    i++;
                }
                Stitches[r].id_attach = Stitches[r].bottomNodesNames.map(b => Stitches[r].bottomNodes[b].id);
            }
        } else if (not_done) {
            if (turn == 1) {
                Psp.reverse();
                if (partialSkip)
                    SP_offset = 1 - SP_offset;
            }
            var i = 0;
            for (let r of c['ref_inds']) {
                let originalBottomNodesNames = [...Stitches[r].bottomNodesNames];
                for (let b of originalBottomNodesNames) {


                    if (L > 1)
                        isp = (i + SP_offset) * (Lsp - 1) / (L - 1);
                    else
                        isp = (0.5) * (Lsp - 1);

                    i0 = Math.floor(isp);
                    i1 = Math.ceil(isp);

                    if (i0 == i1) {
                        Stitches[r].bottomNodes[b].id = Psp[i0];
                    } else {

                        let p0 = Psp[i0];
                        let p1 = Psp[i1];

                        //var pm = p0 + ((p1 - p0) * (isp - i0));

                        let bi = Stitches[r].bottomNodesNames.indexOf(b);
                        Stitches[r].bottomNodesNames.splice(bi, 0, b + '_split_0_');
                        Stitches[r].bottomNodesNames[bi + 1] = b + '_split_1_';
                        Stitches[r].otherNodes[b] = {
                            type: 'hidden'
                        };
                        let depth = Stitches[r].bottomNodes[b].attachment_depth;
                        delete Stitches[r].bottomNodes[b];
                        Stitches[r].bottomNodes[b + '_split_0_'] = {
                            attachment_depth: depth,
                            id: p0
                        };
                        Stitches[r].bottomNodes[b + '_split_1_'] = {
                            attachment_depth: depth,
                            id: p1
                        };

                        //let d = parseFloat(Dictionary['ch'].split('!-')[1]) //find length of chain
                        //Find distance between p0 and p1. 
                        //if (Math.abs(p0 - p1) != 1)
                        //    throw new Error('Cannot use same label over multiple stitches that are not adjacent. Consider using different labels: ' + JSON.stringify(c))

                        let pmax = p0;
                        let pmin = p1;
                        if (p1 > p0) {
                            pmax = p1;
                            pmin = p0;
                        }
                        let [s0, ind1] = find_stitch_by_id(Stitches, pmax);
                        //  console.log('A', s0, ind1, s0.topNodesNames)
                        let name1 = s0.topNodesNames[ind1];
                        let d = 0;

                        if (s0.id.includes(pmin)) { //if p0 and p1 are on the same stitch.
                            let [_, ind0] = find_stitch_by_id(Stitches, pmin);
                            let name0 = s0.topNodesNames[ind0];
                            if (!((name0 + '--' + name1) in s0.connections))
                                throw new Error('Expected connection ' + (name0 + '--' + name1) + ' is missing from stitch: ' + s0);
                            d = s0.connections[name0 + '--' + name1];
                            console.log('debug1', d, s0.connections, name0, name1, ind0, ind1);
                        } else if (s0.id_attach.includes(pmin)) {
                            let letter_bottom = s0.bottomNodesNames.filter(s => s0.bottomNodes[s].id == pmin)[0];
                            if (s0.bottomNodes[letter_bottom].attachment_depth != 1)
                                throw new Error('Cannot use multiple labels across stitches separated by depth more than 1: ' + JSON.stringify(c));
                            let letter_top = s0.topNodesNames.filter(s => s0.topNodes[s].attach == letter_bottom)[0];
                            if (!letter_top)
                                letter_top = s0.topNodesNames[0];
                            if ((letter_bottom + '--' + letter_top) in s0.connections)
                                d = s0.connections[(letter_bottom + '--' + letter_top)];
                            else
                                throw new Error('Cannot find direct connection between stitches using same label. Consider using different labels: ' + JSON.stringify(c));
                        } else if (Math.abs(p0 - p1) == 1) { //if pmax follows the stitch containing pmin
                            if (!(('!--' + name1) in s0.connections))
                                throw new Error('Expected connection ' + ('!--' + name1) + ' is missing from stitch: ' + JSON.stringify(s0));
                            d = s0.connections['!--' + name1];
                            //console.log('debug2', d, s0.connections, name1, ind1)
                        } else
                            throw new Error('Cannot use same label over non-adjacent stitches. Consider using different labels: ' + JSON.stringify(c));

                        //console.log('debug__', d, s0.connections)

                        Stitches[r].connections['*' + b + '_split_0_--' + b] = d * (isp - i0);
                        Stitches[r].connections['*' + b + '_split_1_--' + b] = d * (i1 - isp);

                        let tnn = Stitches[r].topNodesNames.filter(t =>
                            Stitches[r].topNodes[t].attach === b
                        );
                        for (let tn of tnn) {
                            Stitches[r].topNodes[tn].attach = b + '_split_1_';
                        }
                    }
                    i++;
                }
                Stitches[r].id_attach = Stitches[r].bottomNodesNames.map(b => Stitches[r].bottomNodes[b].id);
            }
        }

    }
    return Stitches;
}

function evaluateExpression(expression) {
    return Function(`'use strict'; return ${expression}`)();
}

function update_attachment_points(Stitches, node, attach, turns, attach_row) {
    //console.log(attach, node)
    var at = node['at'];
    //console.log('U: ', at, node, attach, Stitches)
    var key = Object.keys(node['at'])[0]; //assumes node has only one key. Should be true.;;
    at = at[key];
    var Nrows = node['nrow'];

    if (at == null)
        return null;
    if (at === '') {
        let direction = 1;
        if (sum(turns.slice(attach_row[key])) % 2 == 1)
            direction = -1;
        attach[key] += direction;
        return attach;
    }
    if (at.includes('][') && (at.slice(-1) == ']')) {
        var at1 = at.split('][')[0] + ']';
        var l = find_label(Stitches, at1);
        var a = l['attach_id'];
        attach_row[key] = find_stitch_by_id(Stitches, a)[0].nrow;
        if (sum(turns.slice(attach_row[key])) % 2 == 0)
            attach[key] = a + (evaluateExpression(at.split('][')[1].slice(0, -1)) - l['n'] + 1);
        else
            attach[key] = a - evaluateExpression(at.split('][')[1].slice(0, -1));
        return attach;
    }
    if ((at[0] === '[') && (at.slice(-1) == ']')) {
        at = at.slice(1, -1);
        var count_by_stitch_name = '';
        if (at.includes(':')) {
            count_by_stitch_name = at.split(':')[0].trim(); //handle case such as [sc:0,1] or [sc:@+1];;
            at = at.split(':')[1].trim();
        }
        var x;
        var y;
        var relative_id = -1;

        var atTrue = false;
        if (at.includes('@')) {
            atTrue = true;
            const regex = /@(\d*)/;
            var keyToExtract = at.match(regex)[1];
            if (keyToExtract === '')
                keyToExtract = '0';
            y = evaluateExpression(at.replace(regex, '0'));
            var at3 = attach[keyToExtract];
            if ((!Number.isInteger(at3)) && 'attach_id' in at3)
                at3 = at3['attach_id'];
            relative_id = at3;
            x = find_stitch_by_id(Stitches, relative_id)[0].nrow;
        } else {
            at = at.split(',');
            var [count, first, last] = count_stitches_in_row(Stitches, Nrows);
            y = evaluateExpression(at[1].replace('%', count));
            x = evaluateExpression(at[0].replace('%', Nrows));
        }

        if (x < 0)
            x += Nrows;

        //console.log(x, y, relative_id, count_by_stitch_name, Stitches, node)

        attach_row[key] = x;

        var direction = 1;
        if (sum(turns.slice(x)) % 2 == 1)
            direction = -1;


        if ((atTrue) || count_by_stitch_name !== '')
            attach[key] = find_stitchID_by_pos(Stitches, x, y, relative_id, direction, count_by_stitch_name);
        else
            attach[key] = find_stitchID_by_pos(Stitches, x, y, relative_id, 1, count_by_stitch_name);
        return attach;
    }
    attach[key] = find_label(Stitches, at);
    attach_row[key] = find_stitch_by_id(Stitches, attach[key].attach_id)[0].nrow;
    if (sum(turns.slice(attach_row[key])) % 2 == 1)
        attach[key]['attach_id'] = attach[key].attach_id - attach[key].n + 1;
    return attach;
}

//text = parse_definitions(textSwatch)
//LIST = parse_original_text_to_list_of_structures(text.replace(/ |\t/g, ''))
//parse_StitchCodeList(LIST)


function parse_StitchCodeList(rList) {
    var id = -1;
    var turns = [];
    var attach_row = {
        0: -1
    };
    var attach = {
        0: -1
    };
    var Nrows = 0;
    var Stitches = [];

    for (var row of rList) {
        if (Nrows >= 1) {
            var [count, first, last] = count_stitches_in_row(Stitches, Nrows - 1);
            if (last_element(turns) == 0)
                for (let k of Object.keys(attach)) {
                    attach[k] = first - 1;
                    attach_row[k] = Nrows - 1;
                }
            else
                for (let k of Object.keys(attach)) {
                    attach[k] = last + 1;
                    attach_row[k] = Nrows - 1;
                }
        }
        var k = 0;
        var Stitch;
        for (var node of row) {

            attach = update_attachment_points(Stitches, node, attach, turns, attach_row); //attach now holds the first attachment point of the current node.;;
            //            console.log(node, JSON.stringify(attach), Stitches)

            var key = Object.keys(node['at'])[0];
            if (node['contents'] !== '' && !(['turn'].includes(node['contents']))) {
                //                console.log(JSON.stringify(Stitches), attach, key, attach[key])
                Stitch = parse_StitchCode(node, id, attach[key], Stitches, turns);
                if (Stitch.id_attach.length > 0) {
                    attach[key] = last_element(Stitch.id_attach);
                } else {
                    //Undoing default shift by one if no attachment points.
                    if (node['at'][key] === '') {
                        let direction = 1;
                        if (sum(turns.slice(attach_row[key])) % 2 == 1)
                            direction = -1;
                        attach[key] -= direction;
                    }
                }
                if (Stitch.id.length > 0)
                    id = last_element(Stitch.id);
                Stitches.push(Stitch);
            } else {
                if (attach[key]['attach_id'])
                    attach[key] = attach[key]['attach_id'];
            }
            if ((node['contents'] === 'turn') || k > 0)
                k++;
        }
        if (k > 1)
            throw new Error('Turning can happen only at the end of a row. Error at : ' + JSON.stringify(row));
        if (last_element(row)['contents'] === 'turn')
            turns.push(1);
        else
            turns.push(0);
        Nrows++;
    }

    DEBUG += '=======After parsing the stitch codes:=======\n' + JSON.stringify(Stitches) + '\n';

    Stitches = find_and_fix_references_in_repeated_labels(Stitches, turns);
    DEBUG += '=======After fixing the references to repeated labels:=======\n' + JSON.stringify(Stitches) + '\n';
    for (var i = 0; i < Stitches.length; i++)
        Stitches[i]['uid'] = i;
    return Stitches;
}

function parse_StitchCode(r, id, id_attach, Stitches, turns) {
    var stitch;
    var attach_ref = null;
    //console.log(id_attach)

    if ((id_attach != '') && (!Number.isInteger(id_attach)) && ('attach_id' in id_attach) && (!(['ch', 'turn'].includes(r['contents'])))) {
        attach_ref = id_attach['attach_ref'];
        id_attach = id_attach['attach_id'];
    }
    var sign = 1;
    var StitchName = r['contents'];
    if (StitchName in Dictionary)
        stitch = Dictionary[StitchName];
    else {
        var N_TogInc = 1;
        var OrigStitchName = StitchName;
        var TogOrInc = StitchName.slice(-3);
        if (['inc', 'tog'].includes(TogOrInc)) {
            let matches = StitchName.slice(0, -3).match(/\d+$/);
            N_TogInc = parseInt(matches[0], 10);
            if (!Number.isNaN(N_TogInc)) {
                let matches1 = StitchName.slice(0, -3).match(/(.*?)(?=\d*$)/);
                StitchName = matches1[0];
            } else
                N_TogInc = 1;
        }

        if (!(StitchName in Dictionary))
            throw new Error('Stitch type not defined in Dictionary. Please, add it. Stitch: ' + r['contents']);
        stitch = Dictionary[StitchName];
        if (N_TogInc > 1) {
            if (TogOrInc === 'tog')
                stitch = handle_Ntog(stitch, N_TogInc);
            else
                stitch = handle_Ninc(stitch, N_TogInc);

            Dictionary[OrigStitchName] = stitch;
        }
    }
    //console.log(r['contents'])
    if (stitch[0] !== '&')
        throw new Error('Stitch code needs to start with &: ' + stitch);
    var [type, Top, bottom, attachments, hidden, cons] = stitch.slice(1).split(/[\^\:~]/g);

    const regex1 = /([A-Z0-9a-z_]+)\(([^\);]*)\)/g;
    var topNodesNames = [];
    var topNodes = {};

    let match;
    var k = 1;
    while (match = regex1.exec(Top)) {
        topNodesNames.push(match[1]);
        topNodes[match[1]] = {};
        topNodes[match[1]] = {
            id: id + k
        };

        let type = match[2];
        if ((!match[2]) || (type.trim().length == 0))
            throw new Error('Type of stitch needs to be specified for all top nodes in parenthesis: ' + stitch);
        //    type = 'hidden'
        topNodes[match[1]]['type'] = type;
        k++;
    }
    if ((k == 1) && (Top.trim().length > 0))
        throw new Error('Top stitch unparseable. Type of stitch needs to be specified for all top nodes in parenthesis: ' + stitch);

    //const regex = /(\d+)?([A-Za-z_0-9]+)/g;
    const regex = /(\d+)?([A-Za-z_0-9]+)\[*([back|front]*)\]*/g;
    const bottomNodesNames = [];

    var bottomNodes = {};
    k = 0;
    if (/[\)\(]/.test(bottom))
        throw new Error('Bottom nodes cannot carry type defined in parenthesis: ' + bottom);
    while (match = regex.exec(bottom)) {
        if (k == 0) {
            if (id_attach > 0) {
                if (sum(turns.slice(find_stitch_by_id(Stitches, id_attach)[0].nrow)) % 2 == 1)
                    sign = -1;
            } else {
                if (sum(turns) % 2 == 1)
                    sign = -1;
            }
        }
        const name = match[2];
        const number = match[1] ? parseInt(match[1]) : 1;
        bottomNodesNames.push(name);

        bottomNodes[name] = {};
        bottomNodes[name]['attachment_depth'] = number;
        bottomNodes[name]['id'] = id_attach + k * sign;
        if (match[3] === 'front')
            bottomNodes[name]['jacobian'] = -1;
        else if (match[3] === 'back')
            bottomNodes[name]['jacobian'] = 1;
        else if (match[3])
            throw new Error('Bottom node loop attachment specification can be either "[front]" or "[back]": ' + stitch);
        k++;
    }

    const regexH = /([A-Z0-9a-z_]+)\(?([^;\)]*)\)?/g;
    otherNodes = {};
    while (match = regexH.exec(hidden)) {
        otherNodes[match[1]] = {};
        let type = match[2];
        if (type.trim().length == 0)
            type = 'hidden';
        otherNodes[match[1]]['type'] = type;
    }

    var label = null;
    var inherit = '';
    var labelToInherit;
    if ((r['dot'] !== '') && (r['dot'] != null)) {
        label = r['dot'];
        /////let k = 0
        /////for (let i = 0; i < label.length; i++)
        /////    if (label[i].includes('^')) {
        /////        inherit = parseInt(label[i].split('^')[1], 10)
        /////        if (Number.isNaN(inherit))
        /////            inherit = -1
        /////        label[i] = label[i].replace(/\^\d*/, '')
        /////        labelToInherit = label[i]
        /////        k++
        /////    }
        /////if (k > 1)
        /////    throw new Error('Cannot have two labels with "^": ' + JSON.stringify(r))
        //if (inherit >= bottomNodesNames.length) //FIXME
        //    throw new Error('No bottom node at index specified after "^": ' + JSON.stringify(r))
        //inheritBname = bottomNodesNames[inherit] // FIXME
    }


    //if ((cons.length > 0) && (cons[0] !== '!'))
    //    throw new Error('First connection should start with previous stitch, denoted with "!": ' + stitch)
    connections = {};
    var conArr = [];
    for (var con of cons.split(';')) {
        if (con.trim().length > 0) {
            let [n0, len, n1] = con.split('-');
            n0 = n0.trim();
            n1 = n1.trim();

            if (len !== 'skip') {
                try {
                    len = evaluateExpression(len);
                } catch (error) {
                    throw new Error('Length of connection is not a parseable number in stitch: ' + stitch);
                }
                //let n0 = con[0]
                //let n1 = con.slice(-1)
                //let len = eval(con.slice(1, -1))
                connections[[n0, n1].join('--')] = len;
                ////if (n0[0] === '*')
                ////    n0 = n0.slice(1)
                ////if (topNodesNames.includes(n1) && bottomNodesNames.includes(n0))
                ////    conArr.push([n1, n0])
            }
        }
    }
    //final(`8ch,turn
    //7sc,dc.B^,turn
    //4sc@B`)

    /////if (typeof(inherit) !== 'string') {
    /////
    /////    conArr.sort((a, b) => {
    /////        if (a[0] === b[0]) {
    /////            return a[1].localeCompare(b[1]);
    /////        }
    /////        return a[0].localeCompare(b[0]);
    /////    });
    /////    let [_, n1] = conArr.slice(inherit)[0]
    /////    //if (bottomNodes[n1].attachment_depth > 1)
    /////    //    throw new Error('Using "^" in a label for a connection of attachment depth>1 is not implemented: ' + JSON.stringify(r))
    /////
    /////    let [s, i] = find_stitch_by_id(Stitches, bottomNodes[n1].id)
    /////    //console.log('AAAAAAAAAAaa', conArr, inherit, n1, bottomNodes[n1].id, JSON.stringify(s))
    /////    if (s.id.length > 1)
    /////        throw new Error('Using "^" in a label for a connection to a multi-top node stitch is not implemented: ' + JSON.stringify(r))
    /////    //console.log('A', s.label[0], Stitches)
    /////    if (!s.label)
    /////        s.label = [labelToInherit]
    /////    else
    /////        s.label.push(labelToInherit)
    /////}

    if (attachments.trim() !== '')
        for (var a of attachments.split(';')) {
            a = a.split('-');
            //console.log('log', a[0], topNodesNames, a[1], bottomNodesNames, topNodesNames.includes(a[0]), bottomNodesNames.includes(a[1]))
            if (!topNodesNames.includes(a[0]) || !bottomNodesNames.includes(a[1]))
                throw new Error('Attachment list in stitch raw format should start with top stitch first, and then bottom stitch: ' + a);
            topNodes[a[0]]['attach'] = a[1];
        }
    var id_attach_arr = Array.from(Array(bottomNodesNames.length), (_, i) => id_attach + i * sign); //id_attach is the first attachment point, so start counting from zero;;
    var id_arr = Array.from(Array(topNodesNames.length), (_, i) => id + i + 1); //id was the previous stitch id. so count from 1.;;



    var Stitch = {
        id: id_arr,
        id_attach: id_attach_arr,
        type: type,
        topNodesNames: topNodesNames, //order
        bottomNodesNames: bottomNodesNames, //order

        topNodes: topNodes,
        bottomNodes: bottomNodes,

        otherNodes: otherNodes,

        connections: connections,
        label: [...label],
        attach_ref: attach_ref,
        context: r['context'],
        low_level_type: stitch,
        nrow: r['nrow'],
        Color: r['Color']
    };
    return Stitch;
}


////////////////////////////////
////////////////////////////////
////////////////////////////////
////////////////////////////////
////////////////////////////////
////////////////////////////////



var DIM = 3;

function parse_definitions(text) {
    var text0 = '';
    EXTRA_DOTS = '';
    let k = 0;

    for (var l of text.split('\\')) {
        if (k % 2 == 0)
            text0 += l;
        k++;
    }
    text = text0;
    text0 = '';


    for (let l of text.split('\n')) {
        if ((l.trim().slice(0, 4) !== 'DEF:') && (l.trim()[0] !== '#') && (l.trim().slice(0, 4) !== 'DOT:')) { //remove lines starting with Def. or #
            let l0 = '';
            for (let c of l) {
                if (c === '#') //remove string after a #
                    break;
                l0 += c;
            }
            text0 += l0 + '\n';
        } else if (l.trim().slice(0, 4) === 'DOT:') {
            EXTRA_DOTS += l.trim().slice(4).split('#')[0].trim() + '\n';
        }
    }
    var name, V, H;
    for (let l of text.split('\n'))
        if (l.trim().slice(0, 4) == 'DEF:') {
            l = l.trim().split('#')[0]; //remove any comments;;
            var [a, b] = l.slice(4).split('=');
            a = a.trim();
            b = b.trim();
            if (b[0] === '&') // Include dictionary entry.
                Dictionary[a] = b;
            else if (b.slice(0, 5) == 'Copy(') {
                try {
                    var spl = b.slice(5, -1).split(',');
                    name = spl[0].trim();
                    H = -1;
                    W = -1;
                    if (spl.length >= 2)
                        H = parseFloat(spl[1]);
                    if (spl.length == 3)
                        W = parseFloat(spl[2]);
                } catch (error) {
                    throw new Error('Changing W,H of stitch requires a definition of the kind: dc=Copy(dc,H,W), with H and W being floats.');
                }

                ////
                var dict;
                if (name in Dictionary)
                    dict = Dictionary[name];
                else {
                    var N_TogInc = 1;
                    var TogOrInc = name.slice(-3);
                    if (['inc', 'tog'].includes(TogOrInc)) {
                        let matches = name.slice(0, -3).match(/\d+$/);
                        N_TogInc = parseInt(matches[0], 10);
                        if (!Number.isNaN(N_TogInc)) {
                            let matches1 = name.slice(0, -3).match(/(.*?)(?=\d*$)/);
                            name = matches1[0];
                        } else
                            N_TogInc = 1;
                    }

                    if (!(name in Dictionary))
                        throw new Error('Stitch type not defined in Dictionary. Please, add it. Stitch: ' + name);
                    dict = Dictionary[name];
                    if (N_TogInc > 1) {
                        if (TogOrInc === 'tog')
                            dict = handle_Ntog(dict, N_TogInc);
                        else
                            dict = handle_Ninc(dict, N_TogInc);
                    }
                }
                ////

                Dictionary[a] = handle_changeHeightWidth(dict, a, H, W);
            } else
                text0 = text0.replace(new RegExp('\\b(\\d*)' + a.trim() + '\\b', 'g'), function(match, p1) {
                    return p1 ? p1 + '(' + b.trim() + ')' : '(' + b.trim() + ')';
                });
        }

    backgroundColor = '';
    if (text0.split('BACKGROUND:').length > 2)
        throw new Error('Background color cannot be defined more than once using BACKGROUND.');
    if (text0.split('BACKGROUND:').length == 2) {
        backgroundColor = text0.split('BACKGROUND:')[1].split('\n')[0].split('#')[0].trim();
        text0 = text0.split('BACKGROUND:')[0] + '\n' + text0.split('BACKGROUND:')[1].split('\n').slice(1).join('\n');
    }


    //hack colors:
    text = '';
    for (let l of text0.split('\n')) {
        if (l.split('COLOR:').length >= 2) {
            let S = l.split('COLOR:');
            let l0 = S[0];
            for (var s of S.slice(1)) {
                let insideColor = 1;
                let col = '';
                let j = 0;
                let t = '';
                while (insideColor > 0 && j < s.length) {

                    t = s[j];
                    j++;
                    if (t === '\n')
                        insideColor = 0;
                    if ((insideColor == 1) && (t) === '(')
                        insideColor = 2;
                    if ((t) === ')')
                        insideColor -= 1;
                    if (([',', ']', '}', ].includes(t)) && insideColor == 1)
                        insideColor = 0;
                    if (insideColor > 0)
                        col += t;
                }
                //                console.log(col)
                l0 += 'COLOR:' + col.replaceAll(',', '~').replace('(', '+').replace(')', '-') + s.slice(col.length);
                //                console.log(l0)
            }
            text += l0 + '\n';
        } else
            text += l + '\n';
    }




    return text.trim();
}


function find_vars(text) {
    var variable_names = [];
    try {
        variable_names = text.match(/(\w+)\s*=/g).map(function(match) {
            return match.replace(/\s*=/, '');
        });
    } catch (error) {}
    variable_names = Array.from(new Set(variable_names));
    return [text, variable_names];
}

function evaluate_indices(text) {
    var variable_names;
    [text, variable_names] = find_vars(text);
    //DEBUG += '=======Repeating expressions in curly brackets:=======\n' + text + '\n'
    for (var v of variable_names) {
        var lines = text.split(new RegExp('\\b' + v + '\\b=', 'g')); //Handle i=0
        var R = lines[0];
        for (var sublines of lines.slice(1)) { //handle i++
            sublines = sublines.trim();
            var i = String(parseInt(sublines, 10)); //sublines.match(/^\d+/)[0]; //Handle i=0;;

            //const pattern = /(k\+\+|--k|k--|\+\+k)/;
            const pattern = new RegExp('(\\\+\\\+' + v + '\\b|--' + v + '\\b|\\b' + v + "--|\\b" + v + '\\\+\\\+|next[ ]+\\b' + v + '\\b|prev[ ]+\\b' + v + '\\b)', 'g');
            var tosplit = sublines.slice(i.length);
            const FirstSplit = tosplit.split(pattern);
            const split = FirstSplit.flatMap(item => item.split(new RegExp('(\\b' + v + '\\b)', 'g')));

            var together = [];
            var s = 0;
            while (s < split.length - 1) {
                if (split[s] == v && split[s + 1] == '++')
                    together.push(v + '++');
                else if (split[s] == v && split[s + 1] == '--')
                    together.push(v + '--');
                else if (split[s] == '++' && split[s + 1] == v)
                    together.push("++" + v);
                else if (split[s].trim() == 'next' && split[s + 1] == v)
                    together.push("++" + v);
                else if (split[s].trim() == 'prev' && split[s + 1] == v)
                    together.push("--" + v);
                else if (split[s] == '--' && split[s + 1] == v)
                    together.push("--" + v);
                else {
                    together.push(split[s]);
                    s--;
                }
                s += 2;
            }
            if (s == split.length - 1)
                together.push(split[s]);
            if (together.join('') != tosplit)
                throw new Error('Splitting into index increments failed: ', tosplit);
            together = together.filter(str => str.trim() !== '');

            var r = '';
            for (let t of together) {
                if (t == v)
                    r += i;
                else if (t == v + '++') {
                    r += i;
                    i = String(Number(i) + 1);
                } else if (t == v + '--') {
                    r += i;
                    i = String(Number(i) - 1);
                } else if (t == '++' + v) {
                    i = String(Number(i) + 1);
                    r += i;
                } else if (t == '--' + v) {
                    i = String(Number(i) - 1);
                    r += i;
                } else
                    r += t;
            }
            R += r;
        }
        text = R;
    }
    var t = text.split(/\$,|,\$|\$/);
    text = t[0];
    for (var tt of t.slice(2).filter((_, i) => i % 2 === 0)) { //Drop the expressions enclosed in $$. Those were evaluated above.
        if ((!['\n', ','].includes(text.slice(-1)[0])) && (!['\n', ','].includes(tt[0])))
            text += ',';
        text += tt;
    }

    var pattern = /\[([^\[\]]+)\]/g;
    var matches = text.matchAll(pattern);
    var m;
    //const parser = math.parser()

    while (m = matches.next(), !m.done) {
        for (let i of m.value[1].split(',')) {
            i = i.split(';')[0];
            if (!(i.includes(':'))) {
                try {
                    if (Number.isInteger(evaluateExpression((i)))) {
                        if (i !== String(evaluateExpression((i)))) {
                            text = text.replaceAll(i, String(evaluateExpression((i)))); //replace any index expressions such as (k+3)%2 that evaluate to integers with the corresponding integers.
                        }
                    }
                } catch (error) {
                    continue;
                }
            }

        }
    }
    text = text.replace(/ /g, '');
    return text.trim();
}

function getMatchingClosingBracket(openingBracket) {
    switch (openingBracket) {
        case '(':
            return ')';
        case '[':
            return ']';
        case '{':
            return '}';
        default:
            return null;
    }
}

function duplicateRepeated_before_evaluating_indices(str, i_start0 = 0, stitch_ind_in_text = []) {
    var main = '';
    var at = '';
    var dot = '';
    var mult = '';
    var multT = true;
    var multTAnyTime = false;
    var dotT = false;
    var atT = false;
    var mainT = false;
    var stack = [];
    var holdT = false;
    var out = '';
    var sep = ',';
    var out1 = '';
    var atOrder = -1;
    var i_start = i_start0;
    var i_start_AT;

    if (str[0] === '\n')
        throw new Error('Expression cannot begin with a new line: ' + str);

    const openingBrackets = ['(', '[', '{'];
    const closingBrackets = [')', ']', '}'];
    for (let i = 0; i < str.length; i++) {
        //console.log(i)

        const char = str[i];
        if (openingBrackets.includes(char)) {
            stack.push(char);
        }
        if ((closingBrackets.includes(char)) && (stack.length > 0) && (char === getMatchingClosingBracket(stack[stack.length - 1]))) {
            stack.pop();
        } else if (closingBrackets.includes(char)) {
            throw new Error('Unbalanced brackets in: ' + str);
        }
        if (char === '*' && (stack.length == 0) && (!multT)) {
            if (mult !== '' && (!multTAnyTime))
                throw new Error('Cannot handle two integers multiplying stitches (e.g. 7sc.A*3). Use parenthesis instead (e.g. [7sc.A]*3): ' + main);
            multTAnyTime = true;
            multT = true;
            holdT = false;
            mainT = false;
            dotT = false;
            atT = false;
        } else if (char === '*' && (stack.length == 0) && (multT)) {
            multT = false;
            mainT = true;

            i_start = i_start0 + i + 1;
            atT = false;
            dotT = false;
        } else if (!/\d|\s/.test(char) && (multT) && ![',', '\n', '@', '.'].includes(char) && i != str.length - 1) {
            if (/[a-zA-Z_]/.test(char) && (mult).trim() !== '')
                holdT = true;
            multT = false;
            mainT = true;

            i_start = i_start0 + i;
            atT = false;
            dotT = false;
            main += char;
        } else if ((char === '@') && (stack.length == 0)) {
            if (dotT)
                atOrder = 2;
            else
                atOrder = 1;
            if (at !== '')
                throw new Error('Multiple labels defined without parenthesis: ' + str);
            atT = true;
            i_start_AT = i_start0 + i;
            multT = false;
            mainT = false;
            dotT = false;
        } else if ((char === '.') && (stack.length == 0)) {
            if (dot !== '')
                throw new Error('Multiple references defined without parenthesis: ' + str);
            atT = false;
            multT = false;
            mainT = false;
            dotT = true;
        } else if ((([',', '\n'].includes(char)) && (stack.length == 0)) || i == str.length - 1) {
            sep = char;
            if (char !== '\n')
                sep = ',';
            //console.log('finish off')
            //console.log('finishing: ', at, dot, main)
            if ((i == str.length - 1) && (![',', '\n'].includes(char))) {
                if (multT && (/\d|\s/.test(char))) {
                    mult += char;
                } else if (dotT) {
                    dot += char;
                } else if (atT) {
                    at += char;
                } else {
                    if (main === '')
                        i_start = i_start0 + i;
                    main += char;
                }
            }
            for (let c of main) {
                if (/ |\t/.test(c))
                    i_start++;
                else
                    break;
            }
            main = main.replace(/ +|\t+/g, "");
            at = at.trim();
            dot = dot.trim();
            mult = mult.trim();

            if ((parseInt(mult, 10) < 0) || (mult !== '' && Number.isNaN(parseInt(mult, 10))))
                throw new Error('Multiplier needs fixing: ' + mult);

            if (parseInt(mult, 10) == 1)
                mult = '';
            if ((mult === '') || parseInt(mult, 10) > 0) {
                if (openingBrackets.includes(main[0]) && closingBrackets.includes(main.slice(-1)[0])) {
                    //console.log('finishing2: ', at, dot, main)
                    if (getMatchingClosingBracket(main[0]) !== main.slice(-1)[0])
                        throw new Error('Unmatched brackets: ' + main);
                    var stitch_ind_in_text_tmp = [];
                    var out0 = duplicateRepeated_before_evaluating_indices(main.slice(1, -1), i_start + 1, stitch_ind_in_text_tmp);
                    //out1 = '[' + out0 + ']'
                    //console.log('bug? ', main, main.slice(1, -1), out1)
                    out1 = '';
                    if (atOrder == 1) {
                        if (at !== '')
                            out1 += '@' + at;
                        if (dot !== '')
                            out1 += '.' + dot;
                    } else {
                        if (dot !== '')
                            out1 += '.' + dot;
                        if (at !== '')
                            out1 += '@' + at;
                    }



                    if ((mult !== '') && (!holdT)) {
                        /// HANDLE ITERATION INTERRUPTION >
                        //out0 = out0.trim()
                        const getIndex = (arr, txt, n) => {
                            let count = 0;
                            for (let i = 0; i < arr.length; i++) {
                                if (arr[i][1] === txt) {
                                    count++;
                                    if (count === n) {
                                        return i;
                                    }
                                }
                            }
                            return -1;
                        };
                        //
                        let out2 = '';
                        var stitch_ind_in_text_tmp2 = [...stitch_ind_in_text_tmp];

                        if (out0.split('>').length > 1) { // handle iteration interruption symbol 
                            let out0a = '';
                            let notdone = 0;
                            let indDrop = -1;
                            for (let h of out0.split('>')) {
                                out0a += h;
                                if (notdone == 0) {
                                    out2 += h;
                                    indDrop++;
                                }
                                if (areBracketsBalanced(out2))
                                    notdone++;
                                if (notdone == 0)
                                    out2 += '>';
                                if (notdone == 1) {
                                    out0a = out0a;
                                    if (last_element(out0a) === ',')
                                        out0a = out0a.slice(0, -1);
                                } else
                                    out0a += '>';
                            }
                            if (indDrop != -1) {

                                //stitch_ind_in_text_tmp2 = [...stitch_ind_in_text_tmp]
                                let ii = getIndex(stitch_ind_in_text_tmp, '>', indDrop + 1);
                                stitch_ind_in_text_tmp.splice(ii, 1);
                                stitch_ind_in_text_tmp2.splice(ii);
                            }
                            out0 = out0a;
                            if (last_element(out0) === '>')
                                out0 = out0.slice(0, -1);
                            out2 = out2;
                            if (last_element(out2) === ',')
                                out2 = out2.slice(0, -1);
                        } else
                            out2 = out0;

                        /// HANDLE ITERATION INTERRUPTION <
                        let outM1 = '';
                        var stitch_ind_in_text_tmpM1 = [...stitch_ind_in_text_tmp];

                        if (out0.split('<').length > 1) { // handle iteration interruption symbol  <
                            let out0a = '';
                            let notdone = 0;
                            let indDrop = -1;
                            let i_drop_out2 = 0;
                            for (let h of out0.split('<')) {
                                out0a += h;
                                if (notdone == 0) {
                                    indDrop++;
                                    i_drop_out2 = out0a.length;
                                }
                                if (notdone > 0)
                                    outM1 += h + '<';
                                if (areBracketsBalanced(out0a))
                                    notdone++;
                                if (notdone == 1) {
                                    out0a = out0a;
                                    if (last_element(out0a) === ',')
                                        out0a = out0a.slice(0, -1);
                                } else
                                    out0a += '<';
                            }
                            if (indDrop != -1) {
                                let ii = getIndex(stitch_ind_in_text_tmp, '<', indDrop + 1);
                                stitch_ind_in_text_tmp.splice(ii, 1);
                                stitch_ind_in_text_tmp2.splice(ii, 1);
                                stitch_ind_in_text_tmpM1 = stitch_ind_in_text_tmpM1.slice(ii + 1);

                                out2 = out2.slice(0, i_drop_out2) + out2.slice(i_drop_out2 + 1);
                            }
                            out0 = out0a;
                            if (out0[0] === '<')
                                out0 = out0.slice(1);
                            if (last_element(out0) === '<')
                                out0 = out0.slice(0, -1);
                            outM1 = outM1;
                            if (last_element(outM1) === ',' || last_element(outM1) === '<')
                                outM1 = outM1.slice(0, -1);
                            if (outM1[0] === ',')
                                outM1 = outM1.slice(1);
                        } else
                            outM1 = out0;
                        ///////
                        outM1 = '[' + outM1 + ']' + out1;
                        out2 = '[' + out2 + ']' + out1;
                        out1 = '[' + out0 + ']' + out1;
                        out1 = outM1 + ',' + (out1 + ',').repeat(parseInt(mult, 10) - 2) + out2 + sep;
                        stitch_ind_in_text_tmp = Array((parseInt(mult, 10) - 2)).fill(stitch_ind_in_text_tmp).flat().concat(stitch_ind_in_text_tmp2);
                        stitch_ind_in_text_tmp = stitch_ind_in_text_tmpM1.concat(stitch_ind_in_text_tmp);
                    } else if (mult !== '') {
                        out1 = '[' + out0 + ']' + out1;
                        out1 = mult + '*' + out1 + sep;
                    } else {
                        out1 = '[' + out0 + ']' + out1;
                        out1 = out1 + sep;
                    }
                    out += out1;
                    let tmp = stitch_ind_in_text.concat(stitch_ind_in_text_tmp);
                    stitch_ind_in_text.splice(0, stitch_ind_in_text.length, ...tmp); //in place!
                } else if (openingBrackets.includes(main[0]) || closingBrackets.includes(main.slice(-1)[0])) {
                    throw new Error('Unbalanced brackets: ' + main);

                } else {

                    out1 = main;

                    if (atOrder == 1) {
                        if (at !== '')
                            out1 += '@' + at;
                        if (dot !== '')
                            out1 += '.' + dot;
                    } else {
                        if (dot !== '')
                            out1 += '.' + dot;
                        if (at !== '')
                            out1 += '@' + at;

                    }

                    if ((mult !== '') && (!holdT)) {
                        out1 = (out1 + ',').repeat(parseInt(mult, 10)).slice(0, -1) + sep;
                        let tmp = stitch_ind_in_text.concat(Array((parseInt(mult, 10) - 1)).fill([i_start, main.trim()]));
                        stitch_ind_in_text.splice(0, stitch_ind_in_text.length, ...tmp);
                        //stitch_ind_in_text.push(...([i_start].repeat(parseInt(mult, 10) - 1)))
                    } else if (mult !== '')
                        out1 = mult + '*' + out1 + sep;
                    else
                        out1 = out1 + sep;
                    out += out1;

                    if ((main.trim() + at.trim() + dot.trim()) !== '') {
                        if (main.trim() === '')
                            i_start = i_start_AT;

                        if (main.trim().slice(0, 4) !== 'DOT:' && main.trim().slice(0, 4) !== 'DEF:' && main.trim().slice(0, 6) !== 'COLOR:' && main.trim()[0] !== '#')
                            stitch_ind_in_text.push([i_start, main.trim()]); ///HERE!;;
                    }
                }
            }
            mult = '';
            dot = '';
            at = '';
            main = '';
            atT = false;
            mainT = false;
            holdT = false;
            multT = true;
            dotT = false;
            multTAnyTime = false;
        } else {
            if (multT) {
                if (!/\d|\s/.test(char))
                    throw new Error('Not a digit in multiplier when a number was expected.');
                mult += char;
            } else if (dotT) {
                dot += char;
            } else if (atT) {
                at += char;
            } else if (mainT)
                main += char;
            else
                throw new Error('Unhandled char at: ' + str);
        }
        //console.log(char, stack, multT, mainT, dotT, atT, 'M: ', mult, 'MA: ', main, 'D: ', dot, 'A: ', at, 'out1: ' + out1, 'out: ' + out)
    }

    if (stack.length != 0) throw new Error('Unbalanced brackets in: ' + str);
    //console.log(main, dot, at)
    if (out.slice(-1) === ',')
        out = out.slice(0, -1);
    //console.log('returning: ', out)
    //console.log(stitch_ind_in_text)
    return out;
}


function which_Nrow(str, i) {
    var n = -1;
    var str1 = str.slice(0, i + 1);
    for (var l of str1.split('\n')) {
        if (/.*[a-zA-Z_\^&\-\/\:;\@\.\*]+.*/.test(l))
            n++;
    }
    return n;
}

function getColorByIndex(index, colorMap) {
    let keys = Object.keys(colorMap).map(Number).filter(key => key <= index);
    let maxKey = Math.max(...keys);
    return colorMap[maxKey];
}


var III = 0;

function parse_text_instruction_to_structure(input, original = '', COLOR = {}) {
    var main = '';
    var at = '';
    var dot = '';
    var mult = '';
    var multT = true;
    var dotT = false;
    var atT = false;
    var mainT = false;
    var stack = [];
    var str = input;


    if (typeof(str) === 'string') {
        COLOR = {
            '-1': '#969696'
        };
        var ind = 0;
        var str0 = '';
        str = str.trim();
        for (let l of str.split('\n')) {
            if (l.split('COLOR:').length >= 2) {
                let ind0 = ind;
                let S = l.split('COLOR:');
                let l0 = S[0];
                for (var s of S.slice(1)) {
                    ind = ind0 + l0.length;
                    let insideColor = 1;
                    let col = '';
                    let t = '';
                    let j = 0;
                    while (insideColor > 0 && j < s.length) {
                        t = s[j];
                        j++;
                        if (t === '\n')
                            insideColor = 0;
                        if ((insideColor == 1) && (t) === '(')
                            insideColor = 2;
                        if ((t) === ')')
                            insideColor -= 1;
                        if (([',', ']', '}', ].includes(t)) && insideColor == 1)
                            insideColor = 0;
                        if (insideColor > 0)
                            col += t;
                    }
                    //console.log(col.replaceAll('~', ',').replace('+', '(').replace('-', ')'))
                    COLOR[ind] = col.replaceAll('~', ',').replace('+', '(').replace('-', ')').trim();
                    l0 += s.slice(col.length);
                }
                if (l0 !== '') {
                    ind = ind0 + l0.length + 1;
                    l = l0;
                    str0 += l + '\n';
                }
            } else if (l !== '') {
                ind += l.length + 1;
                str0 += l + '\n';
            }
        }
        str = str0;
        //console.log(COLOR, str0)
        original = str;
        str = {
            contents: str,
            at: {},
            dot: [],
            index: [0, str.length],
            nrow: 0,
            color: getColorByIndex(0, COLOR)
        };
    }
    var out = [];
    var i_start = str.index[0];
    var i_start_AT = str.index[0];

    const openingBrackets = ['(', '[', '{'];
    const closingBrackets = [')', ']', '}'];
    for (let i = 0; i < str.contents.length; i++) {

        Nrows = which_Nrow(original, i + str.index[0]);


        const char = str.contents[i];
        //console.log('logs: ', char, original[i + str.index[0]])
        if (openingBrackets.includes(char)) {
            stack.push(char);
        }
        if ((closingBrackets.includes(char)) && (stack.length > 0) && (char === getMatchingClosingBracket(stack[stack.length - 1]))) {
            stack.pop();
        } else if (closingBrackets.includes(char)) {
            throw new Error('Unbalanced brackets in: ' + str.contents);
        }
        if (char === '*' && (stack.length == 0) && (!multT)) {
            multT = true;
            mainT = false;
            dotT = false;
            atT = false;
        } else if (char === '*' && (stack.length == 0) && (multT)) {
            multT = false;
            mainT = true;

            i_start = str.index[0] + i + 1;
            atT = false;
            dotT = false;
        } else if (!/\d|\s/.test(char) && (multT) && ![',', '\n', '@', '.'].includes(char) && i != str.contents.length - 1) {
            multT = false;
            mainT = true;

            i_start = str.index[0] + i;
            atT = false;
            dotT = false;
            main += char;
        } else if ((char === '@') && (stack.length == 0)) {
            atT = true;
            i_start_AT = str.index[0] + i;
            multT = false;
            mainT = false;
            dotT = false;
        } else if ((char === '.') && (stack.length == 0)) {
            atT = false;
            multT = false;
            mainT = false;
            dotT = true;
        } else if ((([',', '\n'].includes(char)) && (stack.length == 0)) || i == str.contents.length - 1) {

            if ((i == str.contents.length - 1) && (![',', '\n'].includes(char))) {
                if (multT && (/\d|\s/.test(char))) {
                    mult += char;
                } else if (dotT) {
                    dot += char;
                } else if (atT) {
                    at += char;
                } else {
                    if (main === '')
                        i_start = str.index[0] + i;
                    main += char;
                }
            }
            var at0 = at;
            var dot0 = dot;
            if (at === '') {
                at = str.at;
                if (Object.keys(at).length == 0)
                    at = {
                        0: ''
                    };
            } else {
                var num = parseInt(at, 10);
                if (Number.isNaN(num))
                    at = {
                        0: at
                    };
                else {
                    var at1 = {};
                    at1[num] = at.replace(/^\d+\s*/, '').trim();
                    at = at1;
                }
            }

            for (let c of main) {
                if (/ |\t/.test(c))
                    i_start++;
                else
                    break;
            }
            main = main.replace(/ +|\t+/g, "");

            let tmpDot = [...str.dot];
            if (dot !== '')
                tmpDot.push(dot);
            if (openingBrackets.includes(main[0]) && closingBrackets.includes(main.slice(-1)[0])) {
                if (getMatchingClosingBracket(main[0]) !== main.slice(-1)[0])
                    throw new Error('Unmatched brackets: ' + main);
                let out1 = parse_text_instruction_to_structure({
                    contents: main.slice(1, -1),
                    at: at,
                    dot: tmpDot,
                    nrow: Nrows,
                    index: [i_start + 1, str.index[0] + i]
                }, original, COLOR);

                if (mult !== '')
                    out1 = Array(parseInt(mult, 10)).fill(out1).flat();
                out.push(out1);
            } else if (openingBrackets.includes(main[0]) || closingBrackets.includes(main.slice(-1)[0])) {
                throw new Error('Unbalanced brackets: ' + main);
            } else {
                if ((main.trim() + at0.trim() + dot0.trim()) !== '') {
                    if (main.trim() === '')
                        i_start = i_start_AT;
                    let i0 = i_start - 40;
                    let i1 = str.index[0] + i + 1 + 40;
                    if (i0 < 0) i0 = 0;
                    if (i1 > original.length - 1) i1 = original.length - 1;
                    let i_end = str.index[0] + i + 1;
                    if ([',', '\n'].includes(original.slice(i_end - 1)[0]))
                        i_end--;

                    let context = original.slice(i0, i_start) + "<span style='color: red;'>" + original.slice(i_start, i_end) + "</span>" + original.slice(i_end, i1);
                    context = context.replaceAll('\n', '&crarr;&nbsp;');


                    let start = TextIndex[III][0];
                    let end = TextIndex[III][0] + TextIndex[III][1].length;
                    III++;
                    i0 = start - 40 >= 0 ? start - 40 : 0;
                    i1 = end + 40 < TextToBeIndexed.length ? end + 40 : TextToBeIndexed.length;
                    var context_short = TextToBeIndexed.slice(i0, start) + "<span style='color: red;'>" + TextToBeIndexed.slice(start, end) + "</span>" + TextToBeIndexed.slice(end, i1);
                    context_short = context_short.replaceAll('\n', '&crarr;&nbsp;');

                    // i['context_short'] = context
                    //i['context'] = context
                    //console.log(i_start, getColorByIndex(i_start, COLOR))
                    let out1 = {
                        contents: main,
                        at: at,
                        dot: tmpDot,
                        nrow: Nrows,
                        index: [i_start, str.index[0] + i + 1],
                        context: context_short + '&hellip;<br><b>C2</b>: &hellip;' + context,
                        //context_short: context_short,
                        Color: getColorByIndex(i_start, COLOR)
                    };
                    if (mult !== '')
                        out1 = Array(parseInt(mult, 10)).fill(out1).flat();
                    out.push(out1);
                } else {
                    if (mult.trim() !== '')
                        throw new Error('Multiplier set, but no stitch found: ' + str.contents);
                }
            }
            mult = '';
            dot = '';
            at = '';
            main = '';


            atT = false;
            mainT = false;
            multT = true;
            dotT = false;

        } else {
            if (multT) {
                if (!/\d|\s/.test(char))
                    throw new Error('Not a digit in multiplier when a number was expected.');
                mult += char;
            } else if (dotT) {
                dot += char;
            } else if (atT) {
                at += char;
            } else if (mainT)
                main += char;
            else
                throw new Error('Unhandled char at: ' + str.contents);
        }
    }

    if (stack.length != 0) throw new Error('Unbalanced brackets in: ' + str);
    //console.log(main, dot, at)
    return out;
}
var TextToBeIndexed = '';
var TextIndex = [];

const countOccurrences = (str, char) => {
    return str.split(char).length - 1;
};

function parse_original_text_to_list_of_structures(text) {

    //parse_single_text_instruction_to_structure(((duplicateRepeated(' [ 3[ a \n s ] \n \n ] * 4 ' )))).flat(Infinity)
    //var A = []
    TextToBeIndexed = text;
    TextIndex = [];
    text = duplicateRepeated_before_evaluating_indices(text, 0, TextIndex);
    DEBUG += '=======Text index:=======\n' + TextIndex + '\n';
    let tmp = [];
    let K = 0;
    //console.log(TextIndex)
    for (let t of TextIndex) {
        if (t[1].includes("$"))
            K += countOccurrences(t[1], '$');
        else if (K % 2 == 0)
            tmp.push(t);
    }
    TextIndex.splice(0, TextIndex.length, ...tmp);

    //console.log('A', A)
    DEBUG += '=======After duplicating repeated stitches:=======\n' + text + '\n';
    text = evaluate_indices(text);
    DEBUG += '=======After evaluating indices:=======\n' + text + '\n';
    III = 0;
    var LIST = parse_text_instruction_to_structure(text).flat(Infinity);
    DEBUG += '=======After parsing to structure:=======\n' + JSON.stringify(LIST) + '\n';
    var node = [];
    var nrow = 0;
    var row = [];
    var I = 0;
    for (var i of LIST) {
        //TextToBeIndexed = ''

        if (i.nrow !== nrow) {
            node.push(row);
            row = [];
            nrow = i.nrow;
        }
        row.push(i);
    }
    if (row.length > 0)
        node.push(row);

    STATS = {};
    for (let i = 0; i < node.length; i++) {
        var stat = {};
        for (var j of node[i]) {
            if ((j['contents'] != "") && (!(["turn", "end", "start"].includes(j['contents'])))) {
                if (j['contents'] in stat)
                    stat[j['contents']] += 1;
                else
                    stat[j['contents']] = 1;
            }
        }
        STATS[i] = stat;
    }

    DEBUG += '=======After parsing original text to list of list of instructions:=======\n' + JSON.stringify(node) + '\n';
    return node;
}


function sum(arr) {
    let sum = 0;
    arr.forEach(x => {
        sum += x;
    });
    return sum;
}



function areBracketsBalanced(str) {
    const stack = [];
    const openingBrackets = ['(', '[', '{'];
    const closingBrackets = [')', ']', '}'];
    for (let i = 0; i < str.length; i++) {
        const char = str[i];
        if (openingBrackets.includes(char)) {
            stack.push(char);
        } else if (closingBrackets.includes(char)) {
            const matchingOpeningBracket = openingBrackets[closingBrackets.indexOf(char)];
            if (stack.length === 0 || stack.pop() !== matchingOpeningBracket) {
                return false;
            }
        }
    }
    return stack.length === 0;
}


function final(text) {
    Dictionary = JSON.parse(JSON.stringify(OriginalDictionary));
    text = text.trim();
    DEBUG += '=======Original text:=======\n' + text + '\n';
    if (!(areBracketsBalanced(text)))
        throw new Error('Unbalanced brackets in original text.');
    text = text.replace(/\,*\s*\.\.\.\s*\,*/g, ',');
    if (!(areBracketsBalanced(text)))
        throw new Error('Unbalanced brackets after parsing ellipses.');
    text = parse_definitions(text).replace(/\bnext\s/g, '++').replace('/\bprev\s/g', '--').replace(/ |\t/g, '');
    if (!(areBracketsBalanced(text)))
        throw new Error('Unbalanced brackets in original text after parsing definitions.');
    DEBUG += '=======After parsing definitions:=======\n' + text + '\n';
    LIST = parse_original_text_to_list_of_structures(text);

    Stitches = parse_StitchCodeList(LIST);

    return Stitches;
}

function RoundString(pos) {
    var a = String(Math.round(pos[0] * 1000));
    var after_decimal = a.slice(-3);
    var before_decimal = a.slice(0, -3);
    if (after_decimal === '000')
        a = before_decimal;
    else if (after_decimal === '0')
        a = '0';
    else
        a = before_decimal + '.' + '0'.repeat(3 - after_decimal.length) + after_decimal;

    var b = String(Math.round(pos[1] * 1000));
    after_decimal = b.slice(-3);
    before_decimal = b.slice(0, -3);
    if (after_decimal === '000')
        b = before_decimal;
    else if (after_decimal === '0')
        b = '0';
    else
        b = before_decimal + '.' + '0'.repeat(3 - after_decimal.length) + after_decimal;
    return (a + ',' + b);
}

function findPosByNameFromJson(json, name) {
    //var data = JSON.parse("{" + json + "}");
    var posToFind = "";

    for (var i = 0; i < json.objects.length; i++) {
        if (json.objects[i].name === name.slice(1, -1)) {
            posToFind = json.objects[i].pos;
            break; // Interrupt the search once found
        }
    }

    return posToFind;
    //else
    //    return posToFind.slice(0, 3)
}

function export_to_dot(Stitches, json) {
    //console.log(json)
    //var json = null
    var JACS = [];
    if (json !== '') {
        //json = JSON.parse(json0)
        for (var o of json.objects) {
            var pos = o.pos.split(',').map(Number);
            if (pos.length == 2) {
                pos[2] = 0;
            }
            o['pos'] = [pos[0], pos[1], pos[2]];

        }
        lenF = 1.0;
        for (let o of json.objects) {
            if (DIM == 3)
                o['pos'] = String([o.pos[0] / lenF, o.pos[1] / lenF, o.pos[2] / lenF]);
            else
                o['pos'] = String([o.pos[0] / lenF, o.pos[1] / lenF]);
        }
        //console.log(json)
    }
    var text = '';
    var textS = '';
    //if (!simple)
    text += '{"dimen":"' + String(DIM) + '",\n"elements":[';
    //else
    textS += String(DIM) + '\n';
    k = 0;

    var startID_row = [];
    for (var i = 0; i <= Stitches.slice(-1)[0].nrow; i++) {
        let n = count_stitches_in_row(Stitches, i)[1];
        if (n == -1)
            throw new Error('No stitches in row = ' + i);
        startID_row.push(n);
    }

    //add the nodes
    for (var s of Stitches) {
        for (var ni of s.topNodesNames) {
            let n = s.topNodes[ni];
            let pos = [s.nrow, n.id - startID_row[s.nrow]];
            let name = '"' + String(pos) + '|' + s.uid + '"';
            if (json) {
                let POS = findPosByNameFromJson(json, name);
                //console.log(POS)
                if (POS.length > 0) {
                    //if (!simple)
                    text += ',{"type":"node","name":' + name + ',"label":"' + n.type + '|' + s['context'] + '|' + s['Color'] + '","pos":"' + POS + '!"}\n';
                    //else
                    textS += name + ' {' + POS + '}\n';
                } else {
                    //if (!simple)
                    text += ',{"type":"node","name":' + name + ',"label":"' + n.type + '|' + s['context'] + '|' + s['Color'] + '"}\n';
                    //else
                    textS += name + '\n';
                }
            } else {
                //if (!simple)
                text += ',{"type":"node","name":' + name + ',"label":"' + n.type + '|' + s['context'] + '|' + s['Color'] + '"}\n';
                //else
                textS += name + '\n';
            }
        }
        for (let ni of Object.keys(s.otherNodes)) {
            let n = s.otherNodes[ni];
            let pos;
            if (s.id.length > 0) {
                pos = [s.nrow, s.id[0] - startID_row[s.nrow]];
            } else {
                let sPrev = s;
                while (sPrev.id.length == 0) {
                    sPrev = Stitches[Stitches.indexOf(sPrev) - 1];
                }
                pos = [sPrev.nrow, last_element(sPrev.id) - startID_row[sPrev.nrow]];
            }

            let name = '"' + String(pos) + ni + '|' + s.uid + '"';
            if (json) {
                let POS = findPosByNameFromJson(json, name);
                if (POS.length > 0) {


                    //if (!simple)
                    text += ',{"type":"node","name":' + name + ',"label":"' + n.type + '|' + s['context'] + '|' + s['Color'] + '","pos":"' + POS + '!"';
                    //else
                    textS += name + ' {' + POS + '}';
                } else {

                    //if (!simple)
                    text += ',{"type":"node","name":' + name + ',"label":"' + n.type + '|' + s['context'] + '|' + s['Color'] + '"';
                    //else
                    textS += name;
                }

            } else {
                //if (!simple)
                text += ',{"type":"node","name":' + name + ',"label":"' + n.type + '|' + s['context'] + '|' + s['Color'] + '"';
                //else
                textS += name;
            }

            //if (!simple) {
            if (n.type === 'hidden')
                text += ',"style":"invis","width":"0","height":"0"}\n';
            else
                text += '}\n';
            //} else
            textS += '\n';
        }
    }

    //add the edges
    var BlueConnectionEstablished = {};
    for (let s of Stitches) {
        for (var c of Object.keys(s.connections)) {
            //console.log(s, c)
            let len = s.connections[c];
            var doJacobian = false;
            var bOrig;
            let hidden = false;
            if (c[0] === '*') {
                hidden = true;
                c = c.slice(1);
            }
            let [n0, n1] = c.split('--');
            let pos0;
            if (n0 === '!') {
                if (s.id[0] <= 0)
                    break;
                if (s.id.length > 0) {
                    let x = (find_stitch_by_id(Stitches, s.id[0] - 1))[0];
                    pos0 = String([x.nrow, s.id[0] - 1 - startID_row[x.nrow]]) + '|' + x.uid;
                } else {
                    let sPrev = s;
                    while (sPrev.id.length == 0) {
                        //console.log(sPrev, Stitches.indexOf(sPrev))
                        sPrev = Stitches[Stitches.indexOf(sPrev) - 1];
                    }
                    pos0 = String([sPrev.nrow, last_element(sPrev.id) - startID_row[sPrev.nrow]]) + '|' + sPrev.uid;
                }
            } else if ((s.topNodesNames.length > 0) && s.topNodesNames.includes(n0)) {
                pos0 = String([s.nrow, s.topNodes[n0].id - startID_row[s.nrow]]) + '|' + s.uid;
            } else if (n0 in s.otherNodes) {
                if (s.id.length > 0) {
                    pos0 = String([s.nrow, s.id[0] - startID_row[s.nrow]]) + n0 + '|' + s.uid;
                } else {
                    let sPrev = s;
                    while (sPrev.id.length == 0) {
                        sPrev = Stitches[Stitches.indexOf(sPrev) - 1];
                    }
                    pos0 = String([sPrev.nrow, last_element(sPrev.id) - startID_row[sPrev.nrow]]) + n0 + '|' + s.uid;
                }
            } else if (n0 in s.bottomNodes) {
                let buid = -1;
                let b = s.bottomNodes[n0];
                bOrig = s.bottomNodes[n0];
                let depth = b.attachment_depth - 1;
                while (depth > 0) {
                    let bS = find_stitch_by_id(Stitches, b.id);
                    b = bS[0].bottomNodes[bS[0].topNodes[bS[0].topNodesNames[bS[1]]].attach];
                    buid = bS[0].uid;
                    depth += -1; //b.attachment_depth - 2 //NOT CLEAR WHAT ONE WOULD WANT. FIXME if needed.;;
                }
                if ((typeof(b.id) === 'string') && b.id[0] === '^') {
                    let [id, bottom_attach_node] = b.id.slice(1).split('-');
                    let x = find_stitch_by_id(Stitches, parseInt(id, 10))[0];
                    pos0 = String([x.nrow, parseInt(id, 10) - startID_row[x.nrow]]) + bottom_attach_node + '|' + x.uid;
                } else if ((typeof(b.id) === 'string') && b.id[0] === '$') { //this occurs when attaching to post.
                    let [p0, tmp] = b.id.slice(1).split('--');
                    let [p1, d0, d1] = tmp.split(':');
                    if (p0[0] === '^') {
                        let [id, bottom_attach_node] = p0.slice(1).split('-');
                        let x = find_stitch_by_id(Stitches, parseInt(id, 10))[0];
                        buid = x.uid;
                        p0 = String([x.nrow, parseInt(id, 10) - startID_row[x.nrow]]) + bottom_attach_node + '|' + x.uid;
                        x = find_stitch_by_id(Stitches, parseInt(p1, 10))[0];
                        p1 = String([x.nrow, parseInt(p1, 10) - startID_row[x.nrow]]) + '|' + x.uid;
                        buid += '..' + x.uid;
                    } //else
                    // p0 += '|' + find_stitch_by_id(Stitches, parseInt(p0, 10)).uid
                    if (p1[0] === '^') {
                        let [id, bottom_attach_node] = p1.slice(1).split('-');
                        let x = find_stitch_by_id(Stitches, parseInt(id, 10))[0];
                        p1 = String([x.nrow, parseInt(id, 10) - startID_row[x.nrow]]) + bottom_attach_node + '|' + x.uid;
                        buid = x.uid;
                        x = find_stitch_by_id(Stitches, parseInt(p0, 10))[0];
                        p0 = String([x.nrow, parseInt(p0, 10) - startID_row[x.nrow]]) + '|' + x.uid;
                        buid += '..' + x.uid;
                    } //else
                    //  p1 += '|' + find_stitch_by_id(Stitches, parseInt(p1.split('|')[0], 10)).uid
                    //TOFIX???
                    //if (!simple) {
                    text += '{"type":"edge","tail":"' + p0 + '","head":"' + b.id + '|' + buid + '","penwidth":"1","color":"gray","len":"' + evaluateExpression(d0) + '","label":"' + s['Color'] + '"}\n';
                    text += '{"type":"edge","tail":"' + b.id + '|' + buid + '","head":"' + p1 + '","penwidth":"1","color":"gray","len":"' + evaluateExpression(d1) + '","label":"' + s['Color'] + '"}\n';
                    //} else {
                    textS += '"' + p0 + '" -- "' + b.id + '|' + buid + '" ' + evaluateExpression(d0) + '\n';
                    textS += '"' + b.id + '|' + buid + '" -- "' + p1 + '" ' + evaluateExpression(d1) + '\n';
                    //}

                    let name = '"' + b.id + '|' + buid + '"';
                    if (json) {
                        let POS = findPosByNameFromJson(json, name);
                        if (POS.length > 0) {
                            //if (!simple)
                            text += ',{"type":"node","name":' + name + ',"label":"hidden|' + s['Color'] + '","style":"invis","width":"0","height":"0","pos":"' + POS + '!"}\n';
                            //else
                            textS += name + ' {' + POS + '}\n';
                        } else {
                            //if (!simple)
                            text += ',{"type":"node","name":' + name + ',"label":"hidden|' + s['Color'] + '","style":"invis","width":"0","height":"0"}\n';
                            //else
                            textS += name + '\n';
                        }
                    } else {
                        //if (!simple)
                        text += ',{"type":"node","name":' + name + ',"label":"hidden|' + s['Color'] + '","style":"invis","width":"0","height":"0"}\n';
                        //else
                        textS += name + '\n';
                    }
                    //text += name + ' [label="hidden|' + s['Color'] + '",style=invis,width=0,height=0]\n';
                    pos0 = b.id + '|' + buid;

                    //                    Stitches[r].bottomNodes[b].id = '$' + p0 + '--' + p1 + ':' + String(d * (isp - i0)) + ':' + String(d * (i1 - isp))
                } else {
                    let x = find_stitch_by_id(Stitches, b.id)[0];
                    pos0 = String([x.nrow, b.id - startID_row[x.nrow]]) + '|' + x.uid;
                    if ('jacobian' in bOrig) {
                        doJacobian = true;
                    }
                }
            } else throw new Error('Cannot find node ' + n0 + ' in the connections of stitch: ' + JSON.stringify(s));

            let pos1;
            //console.log(s)
            if (n1 === '!') {
                if (s.id.length > 0) {
                    let x = (find_stitch_by_id(Stitches, s.id[0] - 1))[0];
                    pos1 = String([x.nrow, s.id[0] - 1 - startID_row[x.nrow]]) + '|' + x.uid;
                } else {
                    let sPrev = s;
                    while (sPrev.id.length == 0) {
                        sPrev = Stitches[Stitches.indexOf(sPrev) - 1];
                    }
                    pos1 = String([sPrev.nrow, last_element(sPrev.id) - startID_row[sPrev.nrow]]) + '|' + sPrev.uid;
                }
            } else if ((s.topNodesNames.length > 0) && s.topNodesNames.includes(n1)) {
                pos1 = String([s.nrow, s.topNodes[n1].id - startID_row[s.nrow]]) + '|' + s.uid;
            } else if (n1 in s.otherNodes) {
                if (s.id.length > 0) {
                    pos1 = String([s.nrow, s.id[0] - startID_row[s.nrow]]) + n1 + '|' + s.uid;
                } else {
                    let sPrev = s;
                    while (sPrev.id.length == 0) {
                        sPrev = Stitches[Stitches.indexOf(sPrev) - 1];
                    }
                    pos1 = String([sPrev.nrow, last_element(sPrev.id) - startID_row[sPrev.nrow]]) + n1 + '|' + s.uid;
                }
            } else if (n1 in s.bottomNodes) {
                let b = s.bottomNodes[n1];
                let depth = b.attachment_depth - 1;
                while (depth > 0) {
                    let bS = find_stitch_by_id(Stitches, b.id);
                    b = bS[0].bottomNodes[bS[0].topNodes[bS[0].topNodesNames[bS[1]]].attach];
                    depth += b.attachment_depth - 2;
                }
                let x = find_stitch_by_id(Stitches, b.id)[0];
                pos1 = String([x.nrow, b.id - startID_row[x.nrow]]) + '|' + x.uid;
            } else throw new Error('Cannot find node ' + n1 + ' in the connections of stitch: ' + s);


            if (doJacobian) {
                let name = '"' + pos1 + '_jacobian' + bOrig.jacobian + '"';
                if (json) {
                    let POS = findPosByNameFromJson(json, name);
                    if (POS.length > 0) {
                        text += ',{"type":"node","name":' + name + ',"label":"hidden|' + s['Color'] + '","style":"invis","width":"0","height":"0","pos":"' + POS + '!"}\n';
                        textS += name + ' {' + POS + '}\n';
                    } else {
                        text += ',{"type":"node","name":' + name + ',"label":"hidden|' + s['Color'] + '","style":"invis","width":"0","height":"0"}\n';
                        textS += name + '\n';
                    }
                } else {
                    text += ',{"type":"node","name":' + name + ',"label":"hidden|' + s['Color'] + '","style":"invis","width":"0","height":"0"}\n';
                    textS += name + '\n';
                }
                text += ',{"type":"edge","tail":"' + pos0 + '","head":' + name + ',"penwidth":"4","color":"red","len":"' + 0.2 + '","label":"' + s['Color'] + '"}\n';
                textS += '"' + pos0 + '" -- ' + name + ' ' + 0.2 + '\n';
                JACS.push([pos0, bOrig.jacobian, '"' + pos0 + '"---' + name, name.slice(1, -1)]);
                pos0 = pos1 + '_jacobian' + bOrig.jacobian;
            }

            if (hidden) {
                text += ',{"type":"edge","tail":"' + pos0 + '","head":"' + pos1 + '","penwidth":"1","color":"gray","len":"' + len + '","label":"' + s['Color'] + '"}\n';
            } else if ((!(pos1 in BlueConnectionEstablished)) && ((((n0 === '!') || ((s.topNodesNames.length > 0) && s.topNodesNames.includes(n0))) && ((n1 === '!') || ((s.topNodesNames.length > 0) && s.topNodesNames.includes(n1)))))) {
                text += ',{"type":"edge","tail":"' + pos0 + '","head":"' + pos1 + '","penwidth":"4","color":"blue","len":"' + len + '","label":"' + s['Color'] + '"}\n';
                BlueConnectionEstablished[pos1] = true;
            } else {
                text += ',{"type":"edge","tail":"' + pos0 + '","head":"' + pos1 + '","penwidth":"4","color":"red","len":"' + len + '","label":"' + s['Color'] + '"}\n';
            }
            //} else
            textS += '"' + pos0 + '" -- "' + pos1 + '" ' + len + '\n';
        }
    }
    //if (simple)


    text = text.replace('"elements":[,{"', '"elements":[{"');

    text += ']}';
    if (JACS.length > 0) {
        console.log(text);
        let j = JSON.parse(text);
        console.log(j);
        for (let jac of JACS) {
            let i3 = jac[0];
            let value = jac[1];
            let jtext = jac[2];
            let nodes = findConnectedNodeNames(j, i3);
            if (nodes.blue.length !== 1)
                throw new Error('More than one blue edge connected to ' + i3);
            if (nodes.red.length < 1)
                console.log('Requested back/front loop attachment, but no red edges connected to ' + i3);
            else {
                if (value == 1)
                    textS += '"' + nodes.blue[0] + '"---"' + nodes.red.slice(-1) + '"---' + jtext + '\n';
                else if (value == -1)
                    textS += '"' + nodes.red.slice(-1) + '"---"' + nodes.blue[0] + '"---' + jtext + '\n';
                else
                    throw new Error('Not sure what to do with a Jacobian whose values is not +/-1: ' + jac);
            }
        }
    }
    textS += EXTRA_DOTS;
    DEBUG += '=======After export to dot; simple=false:=======\n' + text + '\n' + '=======After export to dot; simple=true:=======\n' + textS + '\n';
    return [text, textS];
}


function findConnectedNodeNames(json, nodeName) {
    const connectedNodes = {
        red: [],
        blue: [],
        gray: []
    };
    json.elements.forEach(element => {
        if (element.type === 'edge' && element.head === nodeName) {
            const connectedNode = json.elements.find(e => e.name === element.tail);
            if (connectedNode) {
                connectedNodes[element.color].push(connectedNode.name);
            }
        }
    });
    return connectedNodes;
}

function processText(text, json0) {
    text = text.replace(/\t/g, '    ').replace(/\r/g, '');
    DEBUG = '';
    return export_to_dot(final(text), json0);
}