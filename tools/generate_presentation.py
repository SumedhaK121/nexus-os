import sys
import os
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.enum.text import PP_ALIGN
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE

def create_deck(output_paths):
    prs = Presentation()
    # 16:9 Widescreen dimensions
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)

    blank_layout = prs.slide_layouts[6]

    # Color Palette: NEXUS-OS Dark Navy CS Theme
    BG_DARK = RGBColor(11, 19, 43)       # #0B132B
    CARD_BG = RGBColor(22, 32, 56)       # #162038
    CARD_BORDER = RGBColor(38, 53, 84)   # #263554
    TEXT_WHITE = RGBColor(255, 255, 255)
    TEXT_MUTED = RGBColor(148, 163, 184) # #94A3B8
    TEXT_SEC = RGBColor(203, 213, 225)   # #CBD5E1
    BLUE_ACCENT = RGBColor(56, 189, 248) # #38BDF8 (Sky blue)
    GREEN_ACCENT = RGBColor(34, 197, 94) # #22C55E (Emerald green)
    AMBER_ACCENT = RGBColor(251, 191, 36)# #FBBF24 (Amber)
    RED_ACCENT = RGBColor(239, 68, 68)   # #EF4444 (Red)

    def set_bg(slide):
        bg = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, Inches(13.333), Inches(7.5))
        bg.fill.solid()
        bg.fill.fore_color.rgb = BG_DARK
        bg.line.fill.background()
        return bg

    def add_header(slide, tag_text, title_text):
        # Category Tag
        tag_box = slide.shapes.add_textbox(Inches(0.8), Inches(0.4), Inches(11.733), Inches(0.35))
        tf_tag = tag_box.text_frame
        tf_tag.word_wrap = True
        tf_tag.margin_left = tf_tag.margin_top = tf_tag.margin_right = tf_tag.margin_bottom = 0
        p_tag = tf_tag.paragraphs[0]
        p_tag.text = tag_text.upper()
        p_tag.font.size = Pt(10)
        p_tag.font.bold = True
        p_tag.font.color.rgb = BLUE_ACCENT

        # Slide Title
        title_box = slide.shapes.add_textbox(Inches(0.8), Inches(0.75), Inches(11.733), Inches(0.65))
        tf_title = title_box.text_frame
        tf_title.word_wrap = True
        tf_title.margin_left = tf_title.margin_top = tf_title.margin_right = tf_title.margin_bottom = 0
        p_title = tf_title.paragraphs[0]
        p_title.text = title_text
        p_title.font.size = Pt(22)
        p_title.font.bold = True
        p_title.font.color.rgb = TEXT_WHITE

    def add_card(slide, left, top, width, height, title="", title_color=BLUE_ACCENT):
        card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, width, height)
        card.fill.solid()
        card.fill.fore_color.rgb = CARD_BG
        card.line.color.rgb = CARD_BORDER
        card.line.width = Pt(1.5)

        if title:
            tb = slide.shapes.add_textbox(left + Inches(0.25), top + Inches(0.2), width - Inches(0.5), Inches(0.45))
            tf = tb.text_frame
            tf.word_wrap = True
            tf.margin_left = tf.margin_top = tf.margin_right = tf.margin_bottom = 0
            p = tf.paragraphs[0]
            p.text = title
            p.font.size = Pt(14)
            p.font.bold = True
            p.font.color.rgb = title_color
        return card

    # =========================================================================
    # SLIDE 1: Title Slide
    # =========================================================================
    s1 = prs.slides.add_slide(blank_layout)
    set_bg(s1)

    # Accent decorative bar
    bar = s1.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.8), Inches(1.5), Inches(0.12), Inches(3.2))
    bar.fill.solid()
    bar.fill.fore_color.rgb = BLUE_ACCENT
    bar.line.fill.background()

    tb1 = s1.shapes.add_textbox(Inches(1.2), Inches(1.4), Inches(11.3), Inches(4.5))
    tf1 = tb1.text_frame
    tf1.word_wrap = True

    p0 = tf1.paragraphs[0]
    p0.text = "OPERATING SYSTEMS & DISTRIBUTED SYSTEMS (OSDS) CAPSTONE PROJECT"
    p0.font.size = Pt(12)
    p0.font.bold = True
    p0.font.color.rgb = BLUE_ACCENT

    p1 = tf1.add_paragraph()
    p1.text = "NEXUS-OS"
    p1.font.size = Pt(44)
    p1.font.bold = True
    p1.font.color.rgb = TEXT_WHITE
    p1.space_after = Pt(4)

    p2 = tf1.add_paragraph()
    p2.text = "An Educational Distributed Operating System for a Campus Lab Cluster"
    p2.font.size = Pt(20)
    p2.font.color.rgb = TEXT_SEC
    p2.space_after = Pt(20)

    p3 = tf1.add_paragraph()
    p3.text = "Academic Review & Project Evaluation | Third-Year Computer Engineering"
    p3.font.size = Pt(13)
    p3.font.color.rgb = TEXT_MUTED

    # Bottom Highlight Card (Architecture Highlights)
    add_card(s1, Inches(0.8), Inches(5.2), Inches(11.733), Inches(1.5), "Architecture & Implementation Scope")
    tb1_bot = s1.shapes.add_textbox(Inches(1.05), Inches(5.75), Inches(11.2), Inches(0.8))
    tf1_bot = tb1_bot.text_frame
    tf1_bot.word_wrap = True
    tf1_bot.margin_left = tf1_bot.margin_top = 0
    p_bot = tf1_bot.paragraphs[0]
    p_bot.text = "• Centralized Coordinator Control Plane (:9000) & 3 Worker Workstations (:9001, :9002, :9003)\n• Mini Slurm (CPU Scheduling) + Mini HDFS (Block Storage) + Mini Dropbox (Collaborative Vector Sync)\n• 76/76 Unit Tests Passed · Production Web Control Center (:8080) · Live Cloud Deployment on Render"
    p_bot.font.size = Pt(12)
    p_bot.font.color.rgb = TEXT_SEC

    # =========================================================================
    # SLIDE 2: Project Motivation & Campus Lab Architecture
    # =========================================================================
    s2 = prs.slides.add_slide(blank_layout)
    set_bg(s2)
    add_header(s2, "System Architecture & Motivation", "1. Problem Statement & Campus Lab Cluster Architecture")

    # Card 1: The Problem in Campus Labs
    add_card(s2, Inches(0.8), Inches(1.6), Inches(5.6), Inches(5.2), "The Problem in Academic Lab Clusters", AMBER_ACCENT)
    tb2_left = s2.shapes.add_textbox(Inches(1.05), Inches(2.2), Inches(5.1), Inches(4.3))
    tf2_l = tb2_left.text_frame
    tf2_l.word_wrap = True
    tf2_l.margin_left = tf2_l.margin_top = 0

    points_2l = [
        ("Compute Resource Contention", "Uncoordinated student jobs cause starvation, unbounded wait times, and system crashes."),
        ("Deadlock in Multi-Resource Access", "Concurrent execution without admission control leads to circular wait deadlocks across memory, cores, and I/O."),
        ("Data Divergence & Bit Rot", "Shared laboratory datasets are easily overwritten, corrupted, or lost upon single-disk failure."),
        ("Wall-Clock Drift", "Physical workstation clock differences make distributed event debugging and causality analysis impossible.")
    ]
    for i, (title, desc) in enumerate(points_2l):
        p = tf2_l.paragraphs[0] if i == 0 else tf2_l.add_paragraph()
        p.text = f"• {title}: "
        p.font.bold = True
        p.font.size = Pt(12)
        p.font.color.rgb = TEXT_WHITE
        p.space_after = Pt(2)
        
        run = p.add_run()
        run.text = desc
        run.font.bold = False
        run.font.size = Pt(11.5)
        run.font.color.rgb = TEXT_MUTED

    # Card 2: NEXUS-OS Architectural Solution
    add_card(s2, Inches(6.8), Inches(1.6), Inches(5.733), Inches(5.2), "NEXUS-OS Distributed Solution", GREEN_ACCENT)
    tb2_right = s2.shapes.add_textbox(Inches(7.05), Inches(2.2), Inches(5.2), Inches(4.3))
    tf2_r = tb2_right.text_frame
    tf2_r.word_wrap = True
    tf2_r.margin_left = tf2_r.margin_top = 0

    points_2r = [
        ("Centralized Coordinator (:9000)", "Authoritative control plane hosting scheduler, Banker's admission control, DFS catalog, and lock manager."),
        ("3 Dedicated Worker Nodes (:9001-:9003)", "Execute dispatched compute tasks, store 64 KB block replicas, and maintain in-memory caches."),
        ("Live Web Control Center (:8080)", "Real-time single-page dashboard rendering cluster PCB, Gantt chart, WFG, and fault controls."),
        ("Single-Command Deployment", "Complete 5-process cluster launches via `python app.py` across commodity lab hardware with zero external cloud dependencies.")
    ]
    for i, (title, desc) in enumerate(points_2r):
        p = tf2_r.paragraphs[0] if i == 0 else tf2_r.add_paragraph()
        p.text = f"• {title}: "
        p.font.bold = True
        p.font.size = Pt(12)
        p.font.color.rgb = TEXT_WHITE
        p.space_after = Pt(2)
        
        run = p.add_run()
        run.text = desc
        run.font.bold = False
        run.font.size = Pt(11.5)
        run.font.color.rgb = TEXT_MUTED

    # =========================================================================
    # SLIDE 3: OSDS Theoretical Foundation & Mapping
    # =========================================================================
    s3 = prs.slides.add_slide(blank_layout)
    set_bg(s3)
    add_header(s3, "Theoretical Foundation", "2. Core OSDS Concepts & Production Systems Mapping")

    cols_3 = [
        ("Single-Node OS Foundations", BLUE_ACCENT, Inches(0.8), [
            ("CPU Scheduling", "FCFS, SJF, SRTF, RR, Priority+Aging algorithms"),
            ("Process Control Block (PCB)", "Task states, context switching, PID management"),
            ("Deadlock Prevention", "Dijkstra's Banker's Algorithm admission safety"),
            ("Memory & Paging", "FIFO, LRU, Optimal page replacement & Belady's Anomaly"),
            ("Classical Concurrency", "Semaphores, Mutex, Readers-Writers, Dining Philosophers")
        ]),
        ("Distributed Systems Principles", GREEN_ACCENT, Inches(4.75), [
            ("Cluster Coordination", "Centralized control plane, heartbeat failure detection"),
            ("Logical & Vector Clocks", "Lamport total ordering & Fidge-Mattern causality"),
            ("Mutual Exclusion", "Ricart-Agrawala 2(N-1) peer-to-peer RPC protocol"),
            ("Distributed Storage", "Block chunking, 2x pipeline replication, SHA-256 scrubbing"),
            ("Optimistic Concurrency", "Versioned file editing & Vector Clock conflict resolution")
        ]),
        ("Real-World Industrial Parallels", AMBER_ACCENT, Inches(8.7), [
            ("Slurm Workload Manager", "Cluster batch job dispatching & heavy-tailed traces"),
            ("Apache Hadoop HDFS", "NameNode/DataNode architecture & 64 KB block placement"),
            ("Dropbox Sync Engine", "Chunk delta transfers, rsync algorithm & conflicted copies"),
            ("Google Chubby / ZooKeeper", "Named resource leases & failover lease revocation"),
            ("Linux Cgroups & POSIX", "Memory quota limits & zero-copy shared memory IPC")
        ])
    ]

    for title, col, left, items in cols_3:
        add_card(s3, left, Inches(1.6), Inches(3.8), Inches(5.2), title, col)
        tb = s3.shapes.add_textbox(left + Inches(0.2), Inches(2.2), Inches(3.4), Inches(4.3))
        tf = tb.text_frame
        tf.word_wrap = True
        tf.margin_left = tf.margin_top = 0
        for i, (hdr, desc) in enumerate(items):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            p.text = f"• {hdr}\n  "
            p.font.bold = True
            p.font.size = Pt(11)
            p.font.color.rgb = TEXT_WHITE
            p.space_after = Pt(2)
            run = p.add_run()
            run.text = desc
            run.font.bold = False
            run.font.size = Pt(10)
            run.font.color.rgb = TEXT_MUTED

    # =========================================================================
    # SLIDE 4: Distributed Process Management & CPU Scheduling
    # =========================================================================
    s4 = prs.slides.add_slide(blank_layout)
    set_bg(s4)
    add_header(s4, "Process Management & Scheduling", "3. CPU Scheduling Algorithms & Explainable Execution Trace")

    add_card(s4, Inches(0.8), Inches(1.6), Inches(5.6), Inches(5.2), "6 Implemented Scheduling Policies", BLUE_ACCENT)
    tb4_l = s4.shapes.add_textbox(Inches(1.05), Inches(2.2), Inches(5.1), Inches(4.3))
    tf4_l = tb4_l.text_frame
    tf4_l.word_wrap = True
    tf4_l.margin_left = tf4_l.margin_top = 0

    algos = [
        ("FCFS (First-Come, First-Served)", "Simple FIFO ready queue dispatch. Non-preemptive."),
        ("SJF (Shortest Job First)", "Dispatches lowest remaining burst. Minimizes average wait time."),
        ("SRTF (Shortest Remaining Time First)", "Preemptive variant of SJF. Preempts when shorter job arrives."),
        ("Priority Scheduling", "Dispatches highest priority jobs. Susceptible to starvation."),
        ("Priority + Aging", "Increases priority over wait intervals. Starvation-free guarantee."),
        ("Round Robin (RR)", "Preemptive time-slicing (Quantum Q=2). Fair CPU share across jobs.")
    ]
    for i, (name, dsc) in enumerate(algos):
        p = tf4_l.paragraphs[0] if i == 0 else tf4_l.add_paragraph()
        p.text = f"• {name}: "
        p.font.bold = True
        p.font.size = Pt(11)
        p.font.color.rgb = TEXT_WHITE
        p.space_after = Pt(2)
        run = p.add_run()
        run.text = dsc
        run.font.bold = False
        run.font.size = Pt(10.5)
        run.font.color.rgb = TEXT_MUTED

    add_card(s4, Inches(6.8), Inches(1.6), Inches(5.733), Inches(5.2), "PCB Table & Explainable Execution Trace", GREEN_ACCENT)
    tb4_r = s4.shapes.add_textbox(Inches(7.05), Inches(2.2), Inches(5.2), Inches(4.3))
    tf4_r = tb4_r.text_frame
    tf4_r.word_wrap = True
    tf4_r.margin_left = tf4_r.margin_top = 0

    points_4r = [
        ("Factual Task Lifecycle", "Tasks progress strictly through valid states: WAITING → RUNNING → COMPLETED / FAILED. Real node load increments on start, decrements on finish."),
        ("Explainable Execution Trace ('Why this happened')", "Deterministic justification engine explaining why each job was selected (e.g. 'P1 ran first because arrival T=0 under FCFS', 'P2 preempted P1 under SRTF with remaining burst 3 < 4')."),
        ("Live PCB Process Control Blocks", "Inspect PID, Assigned Node, Burst, Priority, State badge, and live control actions (Pause, Resume, Kill)."),
        ("Measured vs Predicted Metrics", "Evaluates theoretical simulator predictions against actual cluster execution timestamps with Real Gantt chart visualization.")
    ]
    for i, (title, desc) in enumerate(points_4r):
        p = tf4_r.paragraphs[0] if i == 0 else tf4_r.add_paragraph()
        p.text = f"• {title}:\n  "
        p.font.bold = True
        p.font.size = Pt(11.5)
        p.font.color.rgb = TEXT_WHITE
        p.space_after = Pt(4)
        run = p.add_run()
        run.text = desc
        run.font.bold = False
        run.font.size = Pt(11)
        run.font.color.rgb = TEXT_MUTED

    # =========================================================================
    # SLIDE 5: Resource Management & Deadlock Handling
    # =========================================================================
    s5 = prs.slides.add_slide(blank_layout)
    set_bg(s5)
    add_header(s5, "Deadlock Avoidance & Recovery", "4. Banker's Algorithm & Wait-For Graph (WFG) Cycle Recovery")

    add_card(s5, Inches(0.8), Inches(1.6), Inches(5.6), Inches(5.2), "Deadlock Avoidance: Banker's Algorithm", BLUE_ACCENT)
    tb5_l = s5.shapes.add_textbox(Inches(1.05), Inches(2.2), Inches(5.1), Inches(4.3))
    tf5_l = tb5_l.text_frame
    tf5_l.word_wrap = True
    tf5_l.margin_left = tf5_l.margin_top = 0

    points_5l = [
        ("Dijkstra's Admission Control", "Pre-allocates model resources (R1: CPU Cores, R2: Memory Frames, R3: I/O Channels) safely."),
        ("Safety Criterion Check", "Need[i][j] = Max[i][j] - Allocation[i][j]. Requests evaluated against Work and Available vectors."),
        ("Safe vs Unsafe State Distinction", "If granting a request preserves a safe sequence (e.g. P1 → P3 → P4 → P0 → P2), it is GRANTED. If granting leaves insufficient resources, it is DENIED."),
        ("Live Matrix Visualization", "Interactive UI displays Allocation, Max, Need matrices, and Available Vector with textbook initial state.")
    ]
    for i, (title, desc) in enumerate(points_5l):
        p = tf5_l.paragraphs[0] if i == 0 else tf5_l.add_paragraph()
        p.text = f"• {title}:\n  "
        p.font.bold = True
        p.font.size = Pt(11.5)
        p.font.color.rgb = TEXT_WHITE
        p.space_after = Pt(4)
        run = p.add_run()
        run.text = desc
        run.font.bold = False
        run.font.size = Pt(11)
        run.font.color.rgb = TEXT_MUTED

    add_card(s5, Inches(6.8), Inches(1.6), Inches(5.733), Inches(5.2), "Deadlock Detection & Victim Selection", RED_ACCENT)
    tb5_r = s5.shapes.add_textbox(Inches(7.05), Inches(2.2), Inches(5.2), Inches(4.3))
    tf5_r = tb5_r.text_frame
    tf5_r.word_wrap = True
    tf5_r.margin_left = tf5_r.margin_top = 0

    points_5r = [
        ("Directed Wait-For Graph (WFG)", "Directed edge Pi → Pj indicates Pi is blocked waiting for a resource or lock held by Pj. Cycles signify deadlock."),
        ("Cycle Detection Engine", "Detects Circular Wait (P1 → P2 → P3 → P1) and dual independent cycles instantly."),
        ("Victim Selection Policies", "Picks optimal victim process according to 3 resource reclamation policies: Youngest Process, Least Work Done, Lowest Priority."),
        ("Cycle Breaking & Recovery", "Terminating victim immediately releases dependencies, transitions WFG to safe green acyclic state, and logs recovery with Lamport timestamp.")
    ]
    for i, (title, desc) in enumerate(points_5r):
        p = tf5_r.paragraphs[0] if i == 0 else tf5_r.add_paragraph()
        p.text = f"• {title}:\n  "
        p.font.bold = True
        p.font.size = Pt(11.5)
        p.font.color.rgb = TEXT_WHITE
        p.space_after = Pt(4)
        run = p.add_run()
        run.text = desc
        run.font.bold = False
        run.font.size = Pt(11)
        run.font.color.rgb = TEXT_MUTED

    # =========================================================================
    # SLIDE 6: Cache & Distributed Memory Management
    # =========================================================================
    s6 = prs.slides.add_slide(blank_layout)
    set_bg(s6)
    add_header(s6, "Memory & Paging", "5. Page Replacement Simulator & Belady's Anomaly Demonstration")

    add_card(s6, Inches(0.8), Inches(1.6), Inches(5.6), Inches(5.2), "Page Replacement Policies", BLUE_ACCENT)
    tb6_l = s6.shapes.add_textbox(Inches(1.05), Inches(2.2), Inches(5.1), Inches(4.3))
    tf6_l = tb6_l.text_frame
    tf6_l.word_wrap = True
    tf6_l.margin_left = tf6_l.margin_top = 0

    points_6l = [
        ("FIFO (First-In, First-Out)", "Evicts the oldest page brought into physical memory frames. Simple queue implementation."),
        ("LRU (Least Recently Used)", "Evicts the page unused for the longest interval. Approximates optimal replacement using temporal locality."),
        ("Optimal (OPT / MIN)", "Evicts the page that will not be accessed for the longest time in future. Serves as theoretical performance upper bound."),
        ("Step-by-Step Frame Inspection", "Visual table displays exact resident pages per step, marking page hits (green) and page faults (red).")
    ]
    for i, (title, desc) in enumerate(points_6l):
        p = tf6_l.paragraphs[0] if i == 0 else tf6_l.add_paragraph()
        p.text = f"• {title}:\n  "
        p.font.bold = True
        p.font.size = Pt(11.5)
        p.font.color.rgb = TEXT_WHITE
        p.space_after = Pt(4)
        run = p.add_run()
        run.text = desc
        run.font.bold = False
        run.font.size = Pt(11)
        run.font.color.rgb = TEXT_MUTED

    add_card(s6, Inches(6.8), Inches(1.6), Inches(5.733), Inches(5.2), "Belady's Anomaly & Distributed Block Cache", AMBER_ACCENT)
    tb6_r = s6.shapes.add_textbox(Inches(7.05), Inches(2.2), Inches(5.2), Inches(4.3))
    tf6_r = tb6_r.text_frame
    tf6_r.word_wrap = True
    tf6_r.margin_left = tf6_r.margin_top = 0

    points_6r = [
        ("Belady's Anomaly Demonstration", "Using canonical reference string [1, 2, 3, 4, 1, 2, 5, 1, 2, 3, 4, 5]: FIFO page faults increase from 9 (3 frames) to 10 (4 frames) when given more memory!"),
        ("Stack Algorithm Contrast", "Proves that stack algorithms (LRU, Optimal) monotonically improve: the set of pages in m frames is always a strict subset of m+1 frames (M(m) ⊆ M(m+1))."),
        ("Distributed Block Cache", "Nodes maintain in-memory block cache (LRU/FIFO) to accelerate repeated file block reads across cluster nodes."),
        ("Telemetry Metrics", "Tracks Cache Hits, Misses, Hit Ratio %, Capacity, and cached block keys in real time.")
    ]
    for i, (title, desc) in enumerate(points_6r):
        p = tf6_r.paragraphs[0] if i == 0 else tf6_r.add_paragraph()
        p.text = f"• {title}:\n  "
        p.font.bold = True
        p.font.size = Pt(11.5)
        p.font.color.rgb = TEXT_WHITE
        p.space_after = Pt(4)
        run = p.add_run()
        run.text = desc
        run.font.bold = False
        run.font.size = Pt(11)
        run.font.color.rgb = TEXT_MUTED

    # =========================================================================
    # SLIDE 7: Distributed Synchronization & Mutual Exclusion
    # =========================================================================
    s7 = prs.slides.add_slide(blank_layout)
    set_bg(s7)
    add_header(s7, "Distributed Synchronization", "6. Ricart-Agrawala Mutual Exclusion & Distributed Leases")

    add_card(s7, Inches(0.8), Inches(1.6), Inches(5.6), Inches(5.2), "Ricart-Agrawala Mutual Exclusion over RPC", GREEN_ACCENT)
    tb7_l = s7.shapes.add_textbox(Inches(1.05), Inches(2.2), Inches(5.1), Inches(4.3))
    tf7_l = tb7_l.text_frame
    tf7_l.word_wrap = True
    tf7_l.margin_left = tf7_l.margin_top = 0

    points_7l = [
        ("Decentralized Peer-to-Peer Protocol", "Eliminates single point of failure and bottleneck of centralized lock coordinators."),
        ("Message Complexity: Exactly 2(N-1)", "Each entry requires (N-1) REQUESTs and (N-1) REPLYs. Outperforms Lamport's algorithm (3(N-1) messages)."),
        ("Lamport Logical Clocks Ordering", "Requests timestamped with Lamport clock T. Lower timestamp wins entry; conflicting nodes defer replies until releasing CS."),
        ("Live Cluster RPC Trace", "Executes real inter-node TCP-JSON RPC messages between worker workstations with deferred reply queueing.")
    ]
    for i, (title, desc) in enumerate(points_7l):
        p = tf7_l.paragraphs[0] if i == 0 else tf7_l.add_paragraph()
        p.text = f"• {title}:\n  "
        p.font.bold = True
        p.font.size = Pt(11.5)
        p.font.color.rgb = TEXT_WHITE
        p.space_after = Pt(4)
        run = p.add_run()
        run.text = desc
        run.font.bold = False
        run.font.size = Pt(11)
        run.font.color.rgb = TEXT_MUTED

    add_card(s7, Inches(6.8), Inches(1.6), Inches(5.733), Inches(5.2), "Distributed Leases & Classical Concurrency", BLUE_ACCENT)
    tb7_r = s7.shapes.add_textbox(Inches(7.05), Inches(2.2), Inches(5.2), Inches(4.3))
    tf7_r = tb7_r.text_frame
    tf7_r.word_wrap = True
    tf7_r.margin_left = tf7_r.margin_top = 0

    points_7r = [
        ("Distributed Lock Manager (DLM)", "Named resource leases (e.g. file:/report.txt) with lease expiration and automatic revocation upon node crash."),
        ("Readers-Writers Starvation Demo", "Contrasts Courtois Reader-Preference (writer starvation under continuous reads) with Writer-Preference (fair progress)."),
        ("Dining Philosophers Problem", "Demonstrates naive circular wait deadlock vs Dijkstra's Resource Hierarchy total ordering (breaks circular wait)."),
        ("Mutex & Storage Race Conditions", "Demonstrates lost updates under unsynchronized concurrent increments vs thread-safe mutex synchronization.")
    ]
    for i, (title, desc) in enumerate(points_7r):
        p = tf7_r.paragraphs[0] if i == 0 else tf7_r.add_paragraph()
        p.text = f"• {title}:\n  "
        p.font.bold = True
        p.font.size = Pt(11.5)
        p.font.color.rgb = TEXT_WHITE
        p.space_after = Pt(4)
        run = p.add_run()
        run.text = desc
        run.font.bold = False
        run.font.size = Pt(11)
        run.font.color.rgb = TEXT_MUTED

    # =========================================================================
    # SLIDE 8: Distributed File System (DFS) & Data Consistency
    # =========================================================================
    s8 = prs.slides.add_slide(blank_layout)
    set_bg(s8)
    add_header(s8, "Distributed Storage & Replication", "7. Block Distributed File System & Conflict Detection")

    add_card(s8, Inches(0.8), Inches(1.6), Inches(5.6), Inches(5.2), "Block Architecture & Pipelined Replication", BLUE_ACCENT)
    tb8_l = s8.shapes.add_textbox(Inches(1.05), Inches(2.2), Inches(5.1), Inches(4.3))
    tf8_l = tb8_l.text_frame
    tf8_l.word_wrap = True
    tf8_l.margin_left = tf8_l.margin_top = 0

    points_8l = [
        ("64 KB Block Chunking", "Large files split into 64 KB content-addressed blocks for parallel multi-node storage and I/O efficiency."),
        ("2x Pipelined Replication (RF=2)", "Blocks written across worker nodes in an ordered pipeline, ensuring zero data loss upon single-node failure."),
        ("SHA-256 Checksum Scrubbing", "Every block is hashed on write. Background scrubber verifies hashes across nodes to detect bit-rot or tampering."),
        ("Self-Healing Re-replication", "Corrupt or missing replicas are automatically rebuilt from healthy surviving copies without manual intervention.")
    ]
    for i, (title, desc) in enumerate(points_8l):
        p = tf8_l.paragraphs[0] if i == 0 else tf8_l.add_paragraph()
        p.text = f"• {title}:\n  "
        p.font.bold = True
        p.font.size = Pt(11.5)
        p.font.color.rgb = TEXT_WHITE
        p.space_after = Pt(4)
        run = p.add_run()
        run.text = desc
        run.font.bold = False
        run.font.size = Pt(11)
        run.font.color.rgb = TEXT_MUTED

    add_card(s8, Inches(6.8), Inches(1.6), Inches(5.733), Inches(5.2), "Collaborative Sync & Vector Clocks", AMBER_ACCENT)
    tb8_r = s8.shapes.add_textbox(Inches(7.05), Inches(2.2), Inches(5.2), Inches(4.3))
    tf8_r = tb8_r.text_frame
    tf8_r.word_wrap = True
    tf8_r.margin_left = tf8_r.margin_top = 0

    points_8r = [
        ("Optimistic Concurrency Control", "Saving from an older file version is rejected as CONFLICT to prevent silent overwrite of teammate edits."),
        ("Fidge-Mattern Vector Clocks", "Events stamped with vector clocks (VC) tracking causal history across nodes and distinguishing concurrent edits (A || B)."),
        ("Dropbox-Style Conflict Copies", "When concurrent offline edits collide, both copies are preserved (e.g. `report (conflict node-2 T=14).txt`) with zero data loss."),
        ("Rsync Delta Transfers", "Only modified 64 KB block chunks are transferred over the network, achieving 50%+ bandwidth savings vs full file copies.")
    ]
    for i, (title, desc) in enumerate(points_8r):
        p = tf8_r.paragraphs[0] if i == 0 else tf8_r.add_paragraph()
        p.text = f"• {title}:\n  "
        p.font.bold = True
        p.font.size = Pt(11.5)
        p.font.color.rgb = TEXT_WHITE
        p.space_after = Pt(4)
        run = p.add_run()
        run.text = desc
        run.font.bold = False
        run.font.size = Pt(11)
        run.font.color.rgb = TEXT_MUTED

    # =========================================================================
    # SLIDE 9: Fault Tolerance, High Availability & IPC/RPC
    # =========================================================================
    s9 = prs.slides.add_slide(blank_layout)
    set_bg(s9)
    add_header(s9, "Fault Tolerance & Communication", "8. Node Failure & Recovery + IPC & RPC Micro-Benchmarks")

    add_card(s9, Inches(0.8), Inches(1.6), Inches(5.6), Inches(5.2), "Worker Node Fault Tolerance & Recovery", GREEN_ACCENT)
    tb9_l = s9.shapes.add_textbox(Inches(1.05), Inches(2.2), Inches(5.1), Inches(4.3))
    tf9_l = tb9_l.text_frame
    tf9_l.word_wrap = True
    tf9_l.margin_left = tf9_l.margin_top = 0

    points_9l = [
        ("3-State Failure Detector", "Heartbeat period: 2.0s. Missed >4.0s → SUSPECT. Missed >6.0s → OFFLINE eviction."),
        ("Automated Task Migration", "When node-2 crashes, the Coordinator reschedules its active/waiting tasks to surviving nodes (node-1 or node-3)."),
        ("Live Status Synchronization", "Simulating failure updates Online Nodes from 3/3 → 2/3 immediately on System Overview and Node Monitor."),
        ("Seamless Node Healing", "Reconnected node re-registers; status returns to 3/3 ONLINE; cluster resource capacity vector is restored.")
    ]
    for i, (title, desc) in enumerate(points_9l):
        p = tf9_l.paragraphs[0] if i == 0 else tf9_l.add_paragraph()
        p.text = f"• {title}:\n  "
        p.font.bold = True
        p.font.size = Pt(11.5)
        p.font.color.rgb = TEXT_WHITE
        p.space_after = Pt(4)
        run = p.add_run()
        run.text = desc
        run.font.bold = False
        run.font.size = Pt(11)
        run.font.color.rgb = TEXT_MUTED

    add_card(s9, Inches(6.8), Inches(1.6), Inches(5.733), Inches(5.2), "IPC & RPC Micro-Benchmarks", BLUE_ACCENT)
    tb9_r = s9.shapes.add_textbox(Inches(7.05), Inches(2.2), Inches(5.2), Inches(4.3))
    tf9_r = tb9_r.text_frame
    tf9_r.word_wrap = True
    tf9_r.margin_left = tf9_r.margin_top = 0

    points_9r = [
        ("IPC: Sockets vs Shared Memory", "Loopback TCP Sockets require user-to-kernel buffer copies. Zero-copy POSIX Shared Memory maps physical RAM directly, achieving 5.5x lower latency and multi-GB/s throughput."),
        ("RPC: TCP-JSON vs gRPC HTTP/2", "Compares text JSON over stream sockets with binary Protocol Buffers over multiplexed HTTP/2. gRPC achieves 2.4x higher throughput and lower serialization overhead."),
        ("Linux Cgroup Memory Isolation", "Aggressive memory leakers are intercepted and terminated by OOM killer (exit 137) without crashing sibling cluster nodes."),
        ("Dual-Clock Telemetry", "Every RPC message and log entry is tagged with Lamport logical time (T) and Fidge-Mattern Vector Clock (VC).")
    ]
    for i, (title, desc) in enumerate(points_9r):
        p = tf9_r.paragraphs[0] if i == 0 else tf9_r.add_paragraph()
        p.text = f"• {title}:\n  "
        p.font.bold = True
        p.font.size = Pt(11.5)
        p.font.color.rgb = TEXT_WHITE
        p.space_after = Pt(4)
        run = p.add_run()
        run.text = desc
        run.font.bold = False
        run.font.size = Pt(11)
        run.font.color.rgb = TEXT_MUTED

    # =========================================================================
    # SLIDE 10: Conclusion & Q&A
    # =========================================================================
    s10 = prs.slides.add_slide(blank_layout)
    set_bg(s10)

    # Accent decorative bar
    bar10 = s10.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.8), Inches(1.5), Inches(0.12), Inches(2.5))
    bar10.fill.solid()
    bar10.fill.fore_color.rgb = GREEN_ACCENT
    bar10.line.fill.background()

    tb10 = s10.shapes.add_textbox(Inches(1.2), Inches(1.4), Inches(11.3), Inches(3.0))
    tf10 = tb10.text_frame
    tf10.word_wrap = True

    p10_0 = tf10.paragraphs[0]
    p10_0.text = "SUMMARY OF ACHIEVEMENTS & CONTRIBUTIONS"
    p10_0.font.size = Pt(12)
    p10_0.font.bold = True
    p10_0.font.color.rgb = GREEN_ACCENT

    p10_1 = tf10.add_paragraph()
    p10_1.text = "Thank You!"
    p10_1.font.size = Pt(40)
    p10_1.font.bold = True
    p10_1.font.color.rgb = TEXT_WHITE
    p10_1.space_after = Pt(4)

    p10_2 = tf10.add_paragraph()
    p10_2.text = "Questions & Answers | Demonstrations Available"
    p10_2.font.size = Pt(18)
    p10_2.font.color.rgb = TEXT_SEC

    # Bottom 3 Cards: Engineering Highlights
    highlights = [
        ("Comprehensive OSDS Integration", "Bridges classical single-host OS algorithms (Banker's, Belady's, Gantt scheduling) with modern distributed systems (Ricart-Agrawala, DFS replication, Vector Clocks).", BLUE_ACCENT, Inches(0.8)),
        ("Engineering Rigor & Verification", "76/76 unit & integration tests passing · Complete 8-scene automated walkthrough (`demo/lab_day.py`) · Micro-benchmarks for IPC and RPC transports.", GREEN_ACCENT, Inches(4.75)),
        ("Production Lab Readiness", "Single-command master launcher (`python app.py`) across local workstations, cloud deployment on Render, and dark-theme real-time control center.", AMBER_ACCENT, Inches(8.7))
    ]

    for h_title, h_desc, h_col, h_left in highlights:
        add_card(s10, h_left, Inches(4.3), Inches(3.8), Inches(2.6), h_title, h_col)
        tb_h = s10.shapes.add_textbox(h_left + Inches(0.2), Inches(4.9), Inches(3.4), Inches(1.8))
        tf_h = tb_h.text_frame
        tf_h.word_wrap = True
        tf_h.margin_left = tf_h.margin_top = 0
        p_h = tf_h.paragraphs[0]
        p_h.text = h_desc
        p_h.font.size = Pt(11)
        p_h.font.color.rgb = TEXT_MUTED

    for out_p in output_paths:
        os.makedirs(os.path.dirname(out_p), exist_ok=True)
        prs.save(out_p)
        print(f"Saved PPTX to: {out_p}")

if __name__ == "__main__":
    out1 = r"C:\Users\Admin\.gemini\antigravity\brain\7c7a5e96-3a5e-4f98-9ddf-eecf22a77086\NEXUS_OS_Project_Presentation.pptx"
    out2 = r"C:\Users\Admin\.gemini\antigravity\scratch\nexus_os\NEXUS_OS_Project_Presentation.pptx"
    create_deck([out1, out2])
