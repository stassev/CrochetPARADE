## CrochetPARADE: Crochet PAttern Renderer, Analyzer and DEbugger

<p xmlns:cc="http://creativecommons.org/ns#" xmlns:dct="http://purl.org/dc/terms/"><span property="dct:title">The CrochetPARADE manual</span> by <span property="cc:attributionName">Svetlin Tassev</span> is licensed under <a href="http://creativecommons.org/licenses/by-nc-sa/4.0/?ref=chooser-v1" target="_blank" rel="license noopener noreferrer" style="display:inline-block;">CC BY-NC-SA 4.0<img style="height:22px!important;margin-left:3px;vertical-align:text-bottom;" src="https://mirrors.creativecommons.org/presskit/icons/cc.svg?ref=chooser-v1"><img style="height:22px!important;margin-left:3px;vertical-align:text-bottom;" src="https://mirrors.creativecommons.org/presskit/icons/by.svg?ref=chooser-v1"><img style="height:22px!important;margin-left:3px;vertical-align:text-bottom;" src="https://mirrors.creativecommons.org/presskit/icons/nc.svg?ref=chooser-v1"><img style="height:22px!important;margin-left:3px;vertical-align:text-bottom;" src="https://mirrors.creativecommons.org/presskit/icons/sa.svg?ref=chooser-v1"></a></p>



Author:  Svetlin Tassev (2023)

This manual covers both the platform as well as the CrochetPARADE grammar.

# Introduction


CrochetPARADE (Crochet PAttern Renderer, Analyzer, and DEbugger) is a platform that allows users to create, visualize, and analyze both 2D and 3D crochet patterns.



### OVERVIEW

CrochetPARADE uses a custom language grammar that allows users to define stitches and stitch patterns. The CrochetPARADE  grammar aims  to ensure accuracy and precision in the crochet pattern instructions, avoiding the ambiguities encountered with instructions in plain English. The code parses and checks any user provided pattern for correctness and then creates a virtual model of the project, which is then rendered in 3D.

After rendering a pattern, users can review ('debug') the final project's shape and make adjustments. The platform identifies overly loose or tight stitches, enabling users to replace them with more suitable ones before crocheting, thus reducing the need for blocking.

CrochetPARADE's export feature allows users to generate an SVG image that shows stitch connections and identifies stitches by their type, row number, and position within a row. The SVG pattern shows the same information as standard crochet diagrams and can be used as a guide when crocheting. Users can also export projects to 3D files that can be imported in <a href="https://www.blender.org">Blender</a> for further manipulation and visualization.


CrochetPARADE includes interactive features such as the ability to rotate, zoom, and pan the 3D view, as well as animating the pattern creation process, which can help in visualizing how stitches attach to each other. Additional features include highlighting and hiding selected stitches, and changing yarn thickness and color. Users can access stitch information by hovering over stitches in the 3D view.

CrochetPARADE performs all calculations locally on your device, ensuring that no data is collected to a central server or transmitted over the internet. As a side effect, the platform can be sluggish on old hardware. Models of patterns involving (tens of) thousands of stitches can take minutes or more to calculate.



### GOALS AND POSSIBLE APPLICATIONS

   * The main goal of CrochetPARADE is to facilitate crochet project design and execution.
   
   * Patterns created with CrochetPARADE can be easily shared,
ensuring they are free from ambiguities or typographic mistakes.
Creators can simply copy and paste the pattern text to share it,
and others can use the CrochetPARADE platform to render the shared text into a model of the pattern exactly as intended by the pattern author.
                
   * CrochetPARADE can be used in education to teach crocheting but also programming skills, since the CrochetPARADE grammar follows rules similar to those of real programming languages.
               
   * The virtual models created by CrochetPARADE can be imported in 3D modelling and CGI software. Picture an animated movie where characters
wear crochet hats and sweaters that match real-world crochet projects.

   * It is probably inevitable that the grammar along with the renderer can allow AI to learn how to write correct crochet instructions of complicated patterns (beyond simple amigurumi) based on general project descriptions.
   
### LICENSE AND COPYRIGHT

   * The website and all of its computational components are free and open source and are released under the <a href="https://www.gnu.org/licenses/gpl-3.0.en.html#license-text">GPLv3 license</a>, with an exception provided for including <a href="https://graphviz.org/">Graphviz</a> as part of the computational engine. This ensures that the platform will be free and open to all in perpetuity.
   * The showcase patterns are either in the public domain (as specified in the pattern description) or are created by the author and are released in the public domain.
   * This user manual which includes a description of the CrochetPARADE grammar is released under the <a href="https://creativecommons.org/licenses/by-nc-sa/4.0/">Creative Commons BY-NC-SA</a> license. The grammar itself cannot be copyrighted and, as any language, is in the public domain.</li>
    
### ACKNOWLEDGEMENTS

CrochetPARADE uses the following libraries: <a href="https://viz-js.com/">Viz.js</a>, <a href="https://svgjs.dev/">SVG.js</a> and
    <a href="https://threejs.org/">three.js</a>.








# tttttt



Each new line is a new row/round. Rows with stitches are enumerated in the editor. The enumeration will be inaccurate if you are repeating rows by multiplying them. One can repeat rows by adding an extra new line in the end, encompassing the whole expression in parenthesis or brackets, and then multiplying by a number.

   ```
   COLOR: color of stitches to follow
   DEF: stitch definition
   DOT: any extra arguments to neato or the dot language
   # This is a comment.
   BACKGROUND:
   ```

The last iteration can be ended prematurely by adding a `>` as in: `[2sc,>,dc]*3` is parsed to `2sc,dc,2sc,dc,2sc`. Similarly, the first iteration can start at a location marked with `<`.

`...` line wrap

## Specifying attachment points

Stitches on a given row/round are automatically attached one-by-one to consecutive stitches in the previous row/round. If the work is turned at the end of a row, then that is taken into account automatically.

However, in crocheting often one needs to attach ("work") new stitches to non-consecutive previous stitches. To allow that, the code allows specifying attachment points after the `@` symbol, following a stitch in a pattern, e.g. `3sc,dc@[-1,3],dc`, which specifies that the attachment point of the dc stitch should be moved to the 4 stitch (stitch and row counting start from zero) of the previous row/round (specified with a negative index: `-1`).  The next `dc` is worked in the stitch after that.

There are different ways of specifying stitch attachment points:

### Direct Attachment: @[2,10]

Direct attachment to a particular stitch coordinate specified as a pair of integers, e.g. `@[2,10]`. The first integer specifies the row/round number. The second integer specifies the stitch in that row. Counting of stitches/rows/rounds starts from 0, so in the example above, the attachment is at the 11-th stitch of the 3-rd row. 

Negatives numbers imply counting from the end, starting with `-1` meaning the last stitch/row/round; `-2` the last but one stitch/row/round, etc. Counting of rows/rounds starts at the beginning of the project. Counting of stitches starts at the first stitch of the row as written down in the instructions. The current stitch row and stitch position can be specified using the `%` symbol, so `@[%,%-3]` implies the current row, three stitches back before the currently worked stitch. 


### Attachment with stitch type counting @[sc:-1,3]

Attachments with a stitch type before a colon specify that the counting of stitches in a row is over stitches of that type. For example, `@[sc:-1,3]` specifies that the current stitch is worked in the 4th single crochet (sc) stitch of the previous row, as opposed to the 4th stitch in general.

### Attachment with Relative Position: @[@+1]

The **last** attachment point is stored in the `@` symbol, which can be referenced in an attachment point. So, for example `dc,dc@[@]` implies that the second `dc` stitch should be worked in the same stitch as the previous `dc` stitch. 

One can go up and down the row by adding integers to `@`. So, `@[@+2]` means attach two stitches after the **last** attachment point. The direction is in the direction in which we are working, so turns are taken into account.

One can also combine relative position identifier with a stitch type identifier. For instance, `@[sc:@+1]` means attach to the next `sc` stitch after the last attachment point. Note that `@[sc:@]` and `@[sc:@+1]` imply the same attachment point (the next `sc`) if the last attachment was **not** at a `sc` stitch. If it were at a `sc` stitch, then `@[sc:@]` refers to attaching to that same stitch, whereas `@[sc:@+1]` implies attaching to the next `sc` in the row.

### Attachment to a label

#### Simple labels

In crocheting, one often uses stitch markers to keep track of particular stitch positions. Similarly, any stitch here can be labeled with a label following a `.`. For example, in `sc,sc.A,2ch` the second `sc` is labeled with a label `A`. A stitch can have multiple labels that have the distributive property. So, `(3ch.A,sc).B` implies that all chains have both labels `A` and `B`, whereas the `sc` stitch carries label `B` only.

One can then work a stitch in that label by attaching to `A` by writing `sc,sc.A,2ch,ss@A`. When multiple similar labels need to be used, one can use labels that differ by internal labels that are integers, such as `sc,sc.A[0],sc,sc,sc.A[1]`. Here `A[0]` and `A[1]` are treated as different labels.

#### Labeled groups of stitches

##### Basics

When multiple stitches carry the same label, we will call that a labeled group. One can attach to the whole group, or particular stitches in the group. For example `5ch.A`, the label `A` refers to the whole 5 chain group. One can envision attaching to the chain space of that group by doing: `5ch.A,dc,2ch,2sc@A`. In this case, both `sc` stitches will attach to the chain-5 space and will be distributed uniformly over that space. If the uniformly distributed positions do not match preexisting nodes of stitches in the labeled group, then  hidden nodes will be created in between and the stitches will attach to those. That assumes all stitches in a labeled group have the same width (stitch height can vary). 

##### Attaching to the the post of a stitch: .A^ .A^1

To attach to the post of a stitch, follow the definition of the label with `^`. An integer can follow `^` specifying which post of the stitch to attach to if more than one. For example:

    8*ch,turn
    7*sc,dc.B^,turn
    5ch,4*sc@B
    
Here is two example with two different posts as attachment points:

    8ch,turn
    6sc,dc2tog.B^0,turn
    5ch,4*sc@B

which can be compared with:

    8ch,turn
    6sc,dc2tog.B^1,turn
    5ch,4*sc@B

##### Skipping border stitches of a group: .A! .A!0 .A!1

If one wants to attach a set of stitches to a stitch group, then the default is that the two border stitches (first and last) of the group are valid attachment points of the set. One may however, want to skip those, and instead attach in the spaces and stitches in between those border stitches. Then adding defining a label, one can add `!` if one wants to skip both bordering stitches, `!0` if one wants to skip the beginning stitch, and `!1` if one wants to skip the last stitch. 

Here is an example:

    
    10ch,turn
    sk,9sc,turn
    ch,2sc,4ch.A!,4sk,3sc,turn
    4ch,5sc@A,4ch,sc

The 5 `sc` stitches will attach in the 4-chain space labeled with `A`, avoiding the first and last `ch`. Render the same instruction set with `4ch.A`, `4ch.A!0`, `4ch.A!1` to see the difference. Note that the reference `@A` should not contain the `!` instruction.

One can combine the `!` modifier with the `^` modifier:

    8*ch,turn
    7*sc,dc.B^!,turn
    5ch,4*sc@B
    
Here is a topology that is a bit more involved:
    
    9ch,turn
    8sc,dc.A^,turn
    4ch,[sc,sc.B^!,sc]@A
    4ch,3sc@B

##### Adding edge stitches to a group: .A+ .A+0 .A+1 .A+! .A+!0

Let's say, you'd like to attach stitches in a chain space. If you want the stitches to fill in the space evenly up to the stitches bordering the chain space, you would have to add the stitches before and/or after the chain space to the labeled chain-space group. That can be cumbersome. So, to do that automatically add a `+` after the chain-space label definition to add both bordering stitches, or `+0`/`+1` to add the previous/next borderingstitch.

Compare the following:

    8ch,turn
    2sc,3ch.C+,2sc,turn
    3ch,5sc@C,sc@[-1,0]

with

    8ch,turn
    2sc,3ch.C+!,2sc,turn 
    3ch,5sc@C,sc@[-1,0]

and with

    8ch,turn
    2sc,3ch.C,2sc,turn
    3ch,5sc@C,sc@[-1,0]
  
  
##### Reversing the order of attaching a set of stitches to a group of stitches: @A~

When attaching a set of stitches to a group of stitches, the code is trying to do its best, to order the attachments in a way that is least disruptive (i.e. twisting) to the project, but sometimes it fails. For example, render the following:

    10ch,turn
    sk,8sc,sc.A!,turn
    4ch.A!,sk,9tr,turn
    1ch,sk,8sc,7sc@A

If you want the 7 `sc` stitches attaching to the 4-chain group be attached in reverse order, then append a `~` to the end of the attachment label, as in:

    10ch,turn
    sk,8sc,sc.A!,turn
    4ch.A!,sk,9tr,turn
    1ch,sk,8sc,7sc@A~

Compare with the result from running the previous set of instructions.

##### Multiple stitch sets attaching to a labeled group: @A[2;1]

If one needs to attach multiple sets of stitches into a labeled stitch group, then the order in which those sets are attached can be specified with a semi-colon as follows: `6dc.A[12],5ch,3sc@A[12;1],3sc@A[12;0]`. In this example, the **second** set of 3 sc stitches will be attached to the **first** 3 dc stitches, and the first 3 sc's will attach to the second 3 sc's. Note that to use this functionality, one needs to have a label with square brackets, such as `A[12]`. If no order is specified, then the stitch sets are attached in the same order as written, so in  `6dc.A[12],5ch,3sc@A[12],3sc@A[12]`, the 6 `sc` stitches attach consecutively in the 6 `dc` stitches. 

Note that each set can be reversed if you append a `~` at the end of the attachment label. Compare:

    10ch,turn
    sk,8sc,sc.A[]!,turn
    4ch.A[]!,sk,9tr,turn
    1ch,sk,8sc,3sc@A[;1]~,4sc@A[;0]

with

    10ch,turn
    sk,8sc,sc.A[]!,turn
    4ch.A[]!,sk,9tr,turn
    1ch,sk,8sc,3sc@A[;1],4sc@A[;0]

##### Attaching to a particular stitch in a labeled group: @A[][2]

If one wants to attach to the `k`-th stitch carrying the same label, then same as above, one needs to have a label with square brackets, such as `A[0]` and the stitch position would follow in another set of square brackets: e.g. `@A[0][k]` attaches to the `k` stitch of the stitch group labeled `A[0]`.

#### Labels with counters: @A[++k] and .A[++k]

Note that often, one needs to create multiple labels in an algorithmic fashion. One can then use a counter (a variable initialized to an integer and then possibly incremented). One initializes the counter by placing the intializing expression between two `$` signs, say `$k=0$` at the beginning of a line. Then one can increment that value by using the `++` or `--` [operators](https://en.wikipedia.org/wiki/Increment_and_decrement_operators) , or writing `prev k` (same as `--k`) or `next k` (same as `++k`). For example, `$m=0$, sc.A[m],sc.A[m++],sc.A[m],sc.A[++m],sc.A[m],sc.A[prev m],sc.A[m]` is evaluated to `sc.A[0],sc.A[0],sc.A[1],sc.A[2],sc.A[2],sc.A[1],sc.A[1]`. 

Note that when distributing labels with counters, the counter is evaluated first before distribution when the stitches are enclosed in parentheses/brackets, or when an integer precedes a stitch without the `*` symbol. So, `$k=0$,2sc.A[k++],(dc,dc).A[k]` evaluates to `sc.A[0],sc.A[0],dc.A[1],dc.A[1]`. If a stitch is multiplied by an integer using the `*` operator, then the label is distributed before evaluating the counter. For example, `$k=1$, 3*dc.A[k++]` evaluates first to `$k=1$,dc.A[k++],dc.A[k++],dc.A[k++]` and then to `dc.A[1],dc.A[2],dc.A[3]`, whereas `$k=1$, 3dc.A[k++]` would evaluate the counter before distributing the label to give `dc.A[1],dc.A[1],dc.A[1]`. 

Note that counter algebra is permitted in the indexing. So, for example `$k=3$,sc@A[(k++)%5]*5` would use the [mod operator](https://en.wikipedia.org/wiki/Modulo) `%`, and would be parsed to `sc@A[3],sc@A[4],sc@A[0],sc@A[1],sc@A[2]`. This is especially useful when going in rounds, and the first label that you attach to is not of index `0`.

### Multiple attachment heads: @0 @1 @2

Note that in crocheting we may be going back and forth between crocheting in different rows, or more generally in different locations in a project. Then to keep track of where we are in those different attachment locations, we can use different "attachment heads", each one labeled with an integer after the `@` symbol (the default `@` implies `@0`). The attachment head counters are independent. So, for example: `sc@[-1,2],dc@1[-2,3],sc@[@+2],dc@1[@1+2],tc` will attach the second `sc` at `[-1,4]`, and the second `dc` at `[-2,5]`; the `tc` will attach to the next stitch on the default head, so to `[-1,5]` (same as `tc@[@+1]`). We can use any of the labeling methods described above with any of the attachment heads.

### Attachment of an empty stitch

One can reset the attachment point anywhere in a row by using an empty stitch. For example, `sc,dc,@[@-1],tr` is equivalent to `sc,dc,tr@[@]`, both forcing the `tr` and `dc` stitches to attach to the same point. The logic is that the last attachment point after `dc`, is shifted back to the attachment of `sc` by the operator `@[@-1]`, so the next stitch `tr` attaches to the attachment point of `dc`. 

## Defining new stitches.

### Creating an alias
   
   If you are using a sequence of stitches over and over again, you may want to create an alias for them. The syntax for that is:

   ```
   DEF: new_stitch_sequence_alias=stitch1,stitch2,...
   #Example:
   DEF: p=3ch,ss@5[%,-4] 
   # Used an arbitrary attachment head 5 (@5), different from the default.
   # This stitch alias is used in the Flower example.
   ```
   
   One can use an alias in a pattern in the same way one uses any stitch, with one notable exception: An alias will increase the stitch count in a row not by 1 but by however many stitches are in the sequence. The way an alias is handled is by a simple string substitution, so the calculated result will not reference the name of the alias in any way.
   
   The stitch alias `p` in the example above is a picot-3 stitch: ch 3,then slip stitch into the stitch preceding the picot stitch. 
   
### Copying a stitch (with modifications).

   Let us say a pattern requires you to use the reverse single crochet stitch (rsc). That stitch has roughly the same overall geometry (height and width) and topology (connectedness) as the single crochet stitch, so you can simply use the sc stitch. However, let us say you would like to use the name rsc in the pattern. Using `DEF: rsc=sc` is an option, but the name `rsc` will not appear in the rendered project. If you would like that name to show up in the rendered project as well, then you can `Copy()` the stitch:
   ```
   DEF: new_stitch=Copy(old_stitch_name)
   # Example:
   DEF: rsc=Copy(sc)
   # This stitch is used in the Hat example.
   ```
   
   If you would like to adjust the height of the newly created or a pre-existing stitch, you could do:
   ```
   DEF: new_stitch=Copy(old_stitch_name,new_height)
   # Example:
   DEF: dc=Copy(dc,3)
   # This stitch modification is used in the Blanket example.
   ```
      
   The example above overwrites the `dc` stitch with a new height of 3 units.
   
   You can also change the width of a stitch: 
   ```
   DEF: new_stitch=Copy(old_stitch_name, new_height, new_width)
   # Example:
   DEF: narrow_sc=Copy(sc,1,0.8)
   # Note: You have to specify the height if you are specifying 
   # the width, as those are positional arguments.
   ```

### Raw stitch definitions and grammar.
   
One can use "raw stitch" grammar to define new stitches in a concise manner. Internally, the code defines basic stitches using that shorthand notation. Stitches written that way are then translated to a JSON format internally. The grammar for defining a new stitch is as follows:

```
DEF: new_stitch=&comment^top_nodes:bottom_nodes~attachments:other_nodes:connections
```

The terms "top nodes" and "bottom nodes" here refer to specific parts of a crochet stitch. The top node corresponds to the top of a crochet stitch, often identified by the 'V' shape formed at the top of the stitch. This is where the hook is inserted when working a traditional crochet stitch. The bottom node, on the other hand, refers to the attachment points of the crochet stitches, which are the top nodes of other stitches previously made.

Here is a breakdown of the different components of a new stitch defined this way:

#### Comment

The comment field is optional and is defined at the beginning of the stitch definition, after the `&` symbol and before the `^` symbol. They can be a brief description of the stitch, but are **not** used in the code. The comment cannot contain any of these characters: `^:~`. For example, in the stitch definition `&a sc cluster of 3 stitches^A(sc):B~A-B:C;D;E;F;G;H:!-1-A;B-1/3-C;C-1/3-D;D-1/3-A;B-1/3-E;E-1/3-F;F-1/3-A;B-1/3-G;G-1/3-H;H-1/3-A`, the string `a sc cluster of 3 stitches` is a comment.

#### Top Nodes

Top nodes are defined after the `^` symbol and are separated by semicolons. Each top node must have a stitch type specified in parentheses after the stitch name. For example, in the stitch definition `&sc2inc^A(sc);B(sc):C~::!-1-A;A-1-B;C-1-A;C-1-B`, `A(sc)` is a top node where `A` is the stitch name and `sc` is the stitch type. The order in which the top nodes are written specifies the order in which they are chained together.

#### Bottom Nodes

Bottom nodes are defined after the first `:` symbol and are separated by semicolons. Unlike top nodes, bottom nodes do not have stitch types specified in parentheses. Instead, they may have an optional number prefix that indicates the attachment depth. For example, in the stitch definition `&funky^A(funky):B;2C;D~A-D::!-1-A;B-1-A;C-1-A;D-1-A`, `B` is a bottom node with an attachment depth of 1 (default when no number is specified), where `C` has an attachment depth of 2, meaning Stitch A attaches to the attachment point  of `C`, and not to `C` directly.

The order in which the bottom nodes are written specifies the attachment order of the current stitch to the top nodes of the previous stitches.
 
#### Attachments

Attachments are defined after the `~` symbol and are separated by semicolons. Each attachment is a pair of top and bottom node names separated by a `-`. The top node name must come first, followed by the bottom node name. For example, in the stitch definition `&ss^A(ss):B~A-B::!-1-A;B-0.4-A`, `A-B` is an attachment indicating that top node `A` is attached to bottom node `B`. This is only used for finding the attachment point of a stitch, which has an attachment depth greater than 1.

#### Other Nodes

Other nodes are defined after the second `:` symbol and are separated by semicolons. Each other node must have a stitch type specified in parentheses after the stitch name. If no stitch type is specified, it defaults to `'hidden'`. For example, in the stitch definition `'&a sc cluster of 3 stitches^A(sc):B~A-B:C;D;E;F;G;H:!-1-A;B-1/3-C;C-1/3-D;D-1/3-A;B-1/3-E;E-1/3-F;F-1/3-A;B-1/3-G;G-1/3-H;H-1/3-A'`, nodes `C` through `H` are all "other" nodes with type set to `hidden`.

#### Connections

Connections are defined after the third `:` symbol and are separated by semicolons. Each connection is a pair of node names separated by a `-`, with a length value in between the hyphens. The first node (the tail of the connection) name must come first, followed by the length value, and then the second node (the head of the connection) name. For example, in the stitch definition `&ss^A(ss):B~A-B::!-1-A;B-0.4-A`, `!-1-A` and `B-0.4-A` are connections indicating that node `!` is connected to node `A` with a length of `1`, and node `B` is connected to node `A` with a length of `0.4`. Note that node `!` represents the previous stitch, which the current stitch is connected to. 

Connections can be hidden, by preceding a connection with a `*`. For example, `*Z-3-F` is hidden, and is only rendered as thin gray threads. 

If one wants to add a top node that is disjoint from the previous top node, then one can use a length of `skip` for that connection. So, for example the internally defined "stitch" `start_anew` is defined as `&start_anew^A(hidden):~::!-skip-A`. Thus, there is no connection between the next stitch and the previous stitch, similar to starting a new part of the project.

      
#. Color

    COLOR: color_name or hex color
   
 The supported colors are any of the ones listed here: https://en.wikipedia.org/wiki/X11_color_names#Color_name_chart
 Hexadecimal color code is also supported.
 For more information, see https://threejs.org/docs/#api/en/math/Color

#. DOT command

    DOT: "3,27B" [label="hidden|"]
    DOT: "1,54" -- "1,44" [color=gray,len=9.0]
    DOT: epsilon=0.0001
    DOT: start=10 # seed


Blender info


## Warnings and pitfalls
do not use variables with the same name as a stitch

do not define stitches with the same name as variables.

@[@...] cannot work without having an explicit/implicit @ after the first stitch of a row.

when subscripting such as @A[N-(k)], put parenthesis, so that js eval does not treat those as strings but as integers.