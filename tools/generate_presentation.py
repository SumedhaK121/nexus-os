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
    BG_DARK = RGBColor(11, 19, 43)        # #0B132B
    CARD_BG = RGBColor(20, 30, 52)        # #141E34 (Single elevated card)
    CARD_BORDER = RGBColor(38, 55, 88)    # #263758
    TEXT_WHITE = RGBColor(255, 255, 255)
    TEXT_BODY = RGBColor(226, 232, 240)   # #E2E8F0
    TEXT_MUTED = RGBColor(148, 163, 184)  # #94A3B8
    BLUE_ACCENT = RGBColor(56, 189, 248)  # #38BDF8 (Sky blue)
    GREEN_ACCENT = RGBColor(34, 197, 94)  # #22C55E (Emerald green)
    AMBER_ACCENT = RGBColor(251, 191, 36) # #FBBF24 (Amber)

    def set_bg(slide):
        bg = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, Inches(13.333), Inches(7.5))
        bg.fill.solid()
        bg.fill.fore_color.rgb = BG_DARK
        bg.line.fill.background()
        return bg

    def add_slide_header(slide, tag_text, title_text):
        # Category Tag
        tag_box = slide.shapes.add_textbox(Inches(0.9), Inches(0.4), Inches(11.5), Inches(0.32))
        tf_tag = tag_box.text_frame
        tf_tag.word_wrap = True
        tf_tag.margin_left = tf_tag.margin_top = tf_tag.margin_right = tf_tag.margin_bottom = 0
        p_tag = tf_tag.paragraphs[0]
        p_tag.text = tag_text.upper()
        p_tag.font.size = Pt(11)
        p_tag.font.bold = True
        p_tag.font.color.rgb = BLUE_ACCENT

        # Slide Title
        title_box = slide.shapes.add_textbox(Inches(0.9), Inches(0.72), Inches(11.5), Inches(0.55))
        tf_title = title_box.text_frame
        tf_title.word_wrap = True
        tf_title.margin_left = tf_title.margin_top = tf_title.margin_right = tf_title.margin_bottom = 0
        p_title = tf_title.paragraphs[0]
        p_title.text = title_text
        p_title.font.size = Pt(22)
        p_title.font.bold = True
        p_title.font.color.rgb = TEXT_WHITE

    def add_single_card(slide, subtitle, bullets, highlight_badge=None):
        """Adds a single unified, clean card container with bullet points."""
        card_left = Inches(0.9)
        card_top = Inches(1.4)
        card_width = Inches(11.533)
        card_height = Inches(5.45)

        card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, card_left, card_top, card_width, card_height)
        card.fill.solid()
        card.fill.fore_color.rgb = CARD_BG
        card.line.color.rgb = CARD_BORDER
        card.line.width = Pt(1.5)

        # Subtitle / OSDS Scope Bar
        sub_box = slide.shapes.add_textbox(card_left + Inches(0.4), card_top + Inches(0.3), card_width - Inches(0.8), Inches(0.4))
        tf_sub = sub_box.text_frame
        tf_sub.word_wrap = True
        tf_sub.margin_left = tf_sub.margin_top = tf_sub.margin_right = tf_sub.margin_bottom = 0
        p_sub = tf_sub.paragraphs[0]
        p_sub.text = subtitle
        p_sub.font.size = Pt(13)
        p_sub.font.bold = True
        p_sub.font.color.rgb = GREEN_ACCENT

        # Bullet container
        body_box = slide.shapes.add_textbox(card_left + Inches(0.4), card_top + Inches(0.85), card_width - Inches(0.8), card_height - Inches(1.1))
        tf = body_box.text_frame
        tf.word_wrap = True
        tf.margin_left = tf.margin_top = tf.margin_right = tf.margin_bottom = 0

        for idx, (lead, body) in enumerate(bullets):
            p = tf.paragraphs[0] if idx == 0 else tf.add_paragraph()
            p.space_after = Pt(14)
            p.space_before = Pt(2)
            
            # Bullet symbol and bold lead text
            run_lead = p.add_run()
            run_lead.text = f"•  {lead}: "
            run_lead.font.bold = True
            run_lead.font.size = Pt(16)
            run_lead.font.color.rgb = BLUE_ACCENT

            # Body explanation text
            run_body = p.add_run()
            run_body.text = body
            run_body.font.bold = False
            run_body.font.size = Pt(16)
            run_body.font.color.rgb = TEXT_BODY

        if highlight_badge:
            # Bottom highlight pill
            badge_box = slide.shapes.add_textbox(card_left + Inches(0.4), card_top + card_height - Inches(0.65), card_width - Inches(0.8), Inches(0.4))
            tf_b = badge_box.text_frame
            tf_b.word_wrap = True
            tf_b.margin_left = tf_b.margin_top = tf_b.margin_right = tf_b.margin_bottom = 0
            p_b = tf_b.paragraphs[0]
            p_b.text = f"KEY TAKEAWAY: {highlight_badge}"
            p_b.font.size = Pt(12)
            p_b.font.bold = True
            p_b.font.color.rgb = AMBER_ACCENT

    # =========================================================================
    # SLIDE 1: Title Slide (Simple & Clean)
    # =========================================================================
    s1 = prs.slides.add_slide(blank_layout)
    set_bg(s1)

    # Accent decorative bar
    bar = s1.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(1.0), Inches(1.6), Inches(0.12), Inches(3.6))
    bar.fill.solid()
    bar.fill.fore_color.rgb = BLUE_ACCENT
    bar.line.fill.background()

    tb1 = s1.shapes.add_textbox(Inches(1.4), Inches(1.5), Inches(10.8), Inches(4.5))
    tf1 = tb1.text_frame
    tf1.word_wrap = True

    p0 = tf1.paragraphs[0]
    p0.text = "OPERATING SYSTEMS & DISTRIBUTED SYSTEMS CAPSTONE PROJECT"
    p0.font.size = Pt(13)
    p0.font.bold = True
    p0.font.color.rgb = BLUE_ACCENT
    p0.space_after = Pt(10)

    p1 = tf1.add_paragraph()
    p1.text = "NEXUS-OS"
    p1.font.size = Pt(44)
    p1.font.bold = True
    p1.font.color.rgb = TEXT_WHITE
    p1.space_after = Pt(6)

    p2 = tf1.add_paragraph()
    p2.text = "An Educational Distributed Operating System for Campus Lab Clusters"
    p2.font.size = Pt(20)
    p2.font.color.rgb = GREEN_ACCENT
    p2.space_after = Pt(22)

    bullets_s1 = [
        "Aggregates idle campus computers into a unified, high-throughput compute cluster",
        "Implements kernel scheduling, deadlock handling, virtual paging, and distributed DFS from scratch",
        "Provides real-time web telemetry for live cluster monitoring and algorithm inspection",
        "Developed and presented by Four-Member Engineering Team | Department of Computer Science & Engineering"
    ]
    for b in bullets_s1:
        p = tf1.add_paragraph()
        p.space_after = Pt(8)
        r = p.add_run()
        r.text = f"•  {b}"
        r.font.size = Pt(15)
        r.font.color.rgb = TEXT_BODY

    # =========================================================================
    # SLIDE 2: Project Motivation & Campus Lab Problem
    # =========================================================================
    s2 = prs.slides.add_slide(blank_layout)
    set_bg(s2)
    add_slide_header(s2, "PROJECT MOTIVATION & PROBLEM STATEMENT", "Transforming Idle Campus Hardware into a Cluster")
    add_single_card(
        s2,
        subtitle="OSDS Focus: Resource Aggregation, Cluster Workload Balancing & Single-System Image",
        bullets=[
            ("The Campus Problem", "College computer labs have dozens of dual/quad-core PCs that remain idle for over 60% of the day while computationally intensive student tasks wait in line."),
            ("Industrial Limitation", "Existing production systems like Kubernetes or Slurm require heavy enterprise setup, high memory overhead, and hide low-level OS algorithms from learners."),
            ("The NEXUS-OS Solution", "We built a lightweight, educational distributed operating system that unifies separate lab workstations into a single cooperative compute cluster."),
            ("Single System Image", "Students submit jobs to one central interface without needing to know which physical machine actually executes their code."),
            ("Core Engineering Objective", "Provide a reliable, live-demonstrable platform that translates textbook operating systems theory into real, running software.")
        ],
        highlight_badge="NEXUS-OS eliminates lab hardware waste by coordinating idle machines as one shared system."
    )

    # =========================================================================
    # SLIDE 3: Overall Cluster Architecture
    # =========================================================================
    s3 = prs.slides.add_slide(blank_layout)
    set_bg(s3)
    add_slide_header(s3, "SYSTEM ARCHITECTURE", "Two-Tier Master-Worker Cluster Architecture")
    add_single_card(
        s3,
        subtitle="OSDS Focus: Coordinator-Worker Topology, RPC Communication & Global State Synchronization",
        bullets=[
            ("Central Coordinator", "Acts as the cluster master. Exposes REST APIs, manages global process queues, executes Banker's algorithm, and tracks active worker nodes."),
            ("Worker Nodes (Node 1, Node 2, Node 3)", "Independent worker daemons running on separate lab machines that pull assigned tasks, execute them, and stream back results."),
            ("Heartbeat Failure Detector", "Each worker transmits heartbeats every 10 seconds. The Coordinator flags any silent node after a 30-second timeout threshold."),
            ("Real-Time Telemetry", "Uses Server-Sent Events (SSE) and asynchronous polling to stream live cluster state, CPU loads, and logs directly to the dashboard."),
            ("Decoupled Design", "Workers can join, leave, or restart dynamically without crashing the coordinator or terminating active cluster management.")
        ],
        highlight_badge="Clear separation between global coordination (Master) and distributed task execution (Workers)."
    )

    # =========================================================================
    # SLIDE 4: Distributed Process Management & CPU Scheduling
    # =========================================================================
    s4 = prs.slides.add_slide(blank_layout)
    set_bg(s4)
    add_slide_header(s4, "MODULE 1: PROCESS MANAGEMENT", "Distributed CPU Scheduling & Process Control")
    add_single_card(
        s4,
        subtitle="OSDS Concepts: Process Control Block (PCB), Preemption, Time Slicing & Starvation Prevention",
        bullets=[
            ("Process Control Block (PCB)", "NEXUS-OS assigns every job a full PCB tracking PID, state, arrival time, burst time, remaining time, priority, and assigned node."),
            ("Deterministic Task States", "Enforces strict finite-state-machine transitions: WAITING -> RUNNING -> COMPLETED (or FAILED on error)."),
            ("6 Implemented Policies", "Supports FCFS, Shortest Job First (SJF), Shortest Remaining Time First (SRTF), Round Robin (Quantum = 4), and Priority Scheduling."),
            ("Priority with Aging", "Low-priority tasks automatically gain priority over time while waiting in queue, mathematically preventing process starvation under heavy load."),
            ("Explainable Execution Trace", "A live dashboard audit log explains exactly why the scheduler picked each task (e.g. quantum expired, shorter remaining burst, priority promotion).")
        ],
        highlight_badge="Tasks transition through validated PCB states with starvation prevention and explainable scheduling."
    )

    # =========================================================================
    # SLIDE 5: Resource Management & Deadlock Handling
    # =========================================================================
    s5 = prs.slides.add_slide(blank_layout)
    set_bg(s5)
    add_slide_header(s5, "MODULE 2: RESOURCE ALLOCATION & DEADLOCKS", "Banker's Algorithm & Wait-For Graph Recovery")
    add_single_card(
        s5,
        subtitle="OSDS Concepts: Dijkstra's Banker's Algorithm, Circular Wait Detection & Victim Preemption",
        bullets=[
            ("Multi-Resource Tracking", "Coordinates shared cluster hardware across three distinct resource vectors: CPU Cores, Memory Blocks, and GPU Slices."),
            ("Banker's Algorithm (Avoidance)", "Before allocating requested resources, the Coordinator calculates whether a safe sequence exists using the condition Need <= Available."),
            ("Unsafe Request Handling", "If granting a request could lead to a deadlock, the allocator safely rejects or defers the request to preserve system stability."),
            ("Wait-For Graph (Detection)", "Maintains a live directed graph where nodes represent processes and directed edges represent blocked resource dependencies."),
            ("Cycle Detection & Recovery", "Runs depth-first search to detect circular wait cycles, automatically terminates the optimal victim process, and reclaims resources to break the deadlock.")
        ],
        highlight_badge="Combines proactive deadlock avoidance (Banker's) with reactive cycle detection and recovery (WFG)."
    )

    # =========================================================================
    # SLIDE 6: Distributed Memory Management & Paging
    # =========================================================================
    s6 = prs.slides.add_slide(blank_layout)
    set_bg(s6)
    add_slide_header(s6, "MODULE 3: MEMORY MANAGEMENT", "Virtual Paging Subsystem & Belady's Anomaly")
    add_single_card(
        s6,
        subtitle="OSDS Concepts: Virtual Memory, Page Frame Allocation, FIFO vs LRU & Belady's Anomaly Proof",
        bullets=[
            ("Virtual Paging Simulation", "Models memory frame allocations (3, 4, or 5 physical frames) against incoming page reference strings submitted by cluster tasks."),
            ("Page Replacement Policies", "Implements First-In First-Out (FIFO), Least Recently Used (LRU), and Optimal Page Replacement (Belady's Min Algorithm) for benchmark comparison."),
            ("Belady's Anomaly Proof", "Our dashboard interactively demonstrates that giving FIFO more memory frames (increasing from 3 to 4) can paradoxically increase page faults from 9 to 10."),
            ("Stack Algorithm Comparison", "Proves why LRU never experiences Belady's Anomaly because its set of resident pages in m frames is always a strict subset of m+1 frames."),
            ("Lab Cluster Impact", "Demonstrates the practical necessity of LRU caching to prevent thrashing and minimize expensive disk swap operations across cluster nodes.")
        ],
        highlight_badge="Interactively proves Belady's Anomaly on FIFO and validates why LRU stack caching prevents thrashing."
    )

    # =========================================================================
    # SLIDE 7: Distributed Synchronization & Mutual Exclusion
    # =========================================================================
    s7 = prs.slides.add_slide(blank_layout)
    set_bg(s7)
    add_slide_header(s7, "MODULE 4: DISTRIBUTED SYNCHRONIZATION", "Ricart-Agrawala Mutual Exclusion & Leases")
    add_single_card(
        s7,
        subtitle="OSDS Concepts: Lamport Logical Clocks, Distributed Critical Section & Fault-Tolerant Leases",
        bullets=[
            ("The Concurrency Problem", "Multiple independent worker nodes must safely access shared hardware and critical sections without a centralized bottleneck or race conditions."),
            ("Ricart-Agrawala Algorithm", "Workers broadcast timestamped request messages to all peers; entry into the critical section is granted only when all peers acknowledge."),
            ("Optimal Message Complexity", "Achieves distributed mutual exclusion with exactly 2(N - 1) network messages per critical section entry."),
            ("Lamport Logical Timestamps", "Breaks concurrent access ties deterministically by comparing message timestamps and unique node identifiers."),
            ("Crash-Resilient Leases", "Protects against node failure during execution: if a node crashes inside the critical section, its time-bounded lease expires and releases the lock automatically.")
        ],
        highlight_badge="Guarantees distributed mutual exclusion using 2(N-1) messages with lease timeouts to prevent orphan locks."
    )

    # =========================================================================
    # SLIDE 8: Distributed File System & Block Storage
    # =========================================================================
    s8 = prs.slides.add_slide(blank_layout)
    set_bg(s8)
    add_slide_header(s8, "MODULE 5: DISTRIBUTED STORAGE", "Fault-Tolerant Block Distributed File System (DFS)")
    add_single_card(
        s8,
        subtitle="OSDS Concepts: Block Chunking, Pipeline Replication, SHA-256 Scrubbing & Vector Clocks",
        bullets=[
            ("64 KB Block Chunking", "Files uploaded to NEXUS-OS are split into uniform 64 KB binary blocks and scattered across physical worker nodes to balance disk usage."),
            ("2x Pipeline Replication", "Every block is stored on a primary worker and replicated to a secondary worker, ensuring files remain fully readable even if any one node crashes."),
            ("SHA-256 Data Scrubbing", "A background integrity scrubber continuously verifies cryptographic checksums to detect and repair silent disk corruption and bitrot."),
            ("Vector Clocks for Concurrency", "Each file block maintains a vector timestamp across nodes to identify and flag conflicting simultaneous writes without data loss."),
            ("High Availability", "Files can be uploaded, listed, and reconstructed seamlessly through the dashboard with zero single-point-of-failure in the storage layer.")
        ],
        highlight_badge="Implements block chunking and 2x replication so student files survive individual disk and node failures."
    )

    # =========================================================================
    # SLIDE 9: Fault Tolerance & IPC Performance
    # =========================================================================
    s9 = prs.slides.add_slide(blank_layout)
    set_bg(s9)
    add_slide_header(s9, "MODULE 6: FAULT TOLERANCE & NETWORKING", "Node Crash Recovery & IPC Micro-Benchmarks")
    add_single_card(
        s9,
        subtitle="OSDS Concepts: Heartbeat Failure Detectors, Dynamic Task Migration & Kernel IPC vs Shared Memory",
        bullets=[
            ("3-State Failure Detector", "The Coordinator continuously tracks worker node health across states: ONLINE -> SUSPECT -> OFFLINE based on missed heartbeats."),
            ("Automated Task Migration", "When a worker failure is detected, the Coordinator stops routing jobs to it and migrates all in-flight tasks to surviving healthy nodes."),
            ("Live Node Recovery", "When an offline worker reconnects, the system resynchronizes state, marks the node healthy (3/3 Online), and redistributes the cluster workload."),
            ("Sockets vs Shared Memory", "Benchmarks demonstrate that POSIX Shared Memory achieves lower latency by avoiding kernel buffer copies and context switches required by TCP Sockets."),
            ("TCP-JSON vs gRPC HTTP/2", "Evaluates serialization overhead: binary Protocol Buffers over multiplexed HTTP/2 deliver superior throughput compared to text JSON streams.")
        ],
        highlight_badge="Demonstrates live node crash handling with task migration, verified by IPC latency benchmarks."
    )

    # =========================================================================
    # SLIDE 10: Conclusion & Engineering Summary
    # =========================================================================
    s10 = prs.slides.add_slide(blank_layout)
    set_bg(s10)
    add_slide_header(s10, "PROJECT EVALUATION & SUMMARY", "Engineering Deliverables & Conclusion")

    # Single Clean Card for Slide 10 with conclusion bullets and Q&A callout
    card_left = Inches(0.9)
    card_top = Inches(1.4)
    card_width = Inches(11.533)
    card_height = Inches(5.45)

    card = s10.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, card_left, card_top, card_width, card_height)
    card.fill.solid()
    card.fill.fore_color.rgb = CARD_BG
    card.line.color.rgb = CARD_BORDER
    card.line.width = Pt(1.5)

    sub_box = s10.shapes.add_textbox(card_left + Inches(0.4), card_top + Inches(0.3), card_width - Inches(0.8), Inches(0.4))
    tf_sub = sub_box.text_frame
    tf_sub.word_wrap = True
    tf_sub.margin_left = tf_sub.margin_top = tf_sub.margin_right = tf_sub.margin_bottom = 0
    p_sub = tf_sub.paragraphs[0]
    p_sub.text = "Summary of Capstone Achievements | NEXUS-OS Distributed Cluster"
    p_sub.font.size = Pt(13)
    p_sub.font.bold = True
    p_sub.font.color.rgb = GREEN_ACCENT

    body_box = s10.shapes.add_textbox(card_left + Inches(0.4), card_top + Inches(0.85), card_width - Inches(0.8), Inches(2.9))
    tf = body_box.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_top = tf.margin_right = tf.margin_bottom = 0

    concl_bullets = [
        ("Full-Stack Distributed OS", "Successfully designed, coded, and deployed a working 4-node cluster (1 Coordinator + 3 Workers) with a live web dashboard."),
        ("10 OSDS Modules Implemented", "Integrated process scheduling, deadlock avoidance, WFG recovery, virtual memory paging, Ricart-Agrawala, and replicated DFS into one unified system."),
        ("Real Algorithms, Zero Mock Data", "Every metric, state transition, and heartbeat reflects genuine algorithmic execution across our backend APIs."),
        ("Resilience & Verification", "Proven reliability under simulated node crashes, in-flight task migration, and heavy burst scheduling workloads.")
    ]

    for idx, (lead, body) in enumerate(concl_bullets):
        p = tf.paragraphs[0] if idx == 0 else tf.add_paragraph()
        p.space_after = Pt(12)
        
        run_lead = p.add_run()
        run_lead.text = f"•  {lead}: "
        run_lead.font.bold = True
        run_lead.font.size = Pt(16)
        run_lead.font.color.rgb = BLUE_ACCENT

        run_body = p.add_run()
        run_body.text = body
        run_body.font.bold = False
        run_body.font.size = Pt(16)
        run_body.font.color.rgb = TEXT_BODY

    # Thank you / Q&A Box
    qa_box = s10.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, card_left + Inches(0.4), card_top + Inches(3.95), card_width - Inches(0.8), Inches(1.15))
    qa_box.fill.solid()
    qa_box.fill.fore_color.rgb = RGBColor(15, 23, 42)
    qa_box.line.color.rgb = BLUE_ACCENT
    qa_box.line.width = Pt(1.5)

    qa_tf = qa_box.text_frame
    qa_tf.word_wrap = True
    p_qa1 = qa_tf.paragraphs[0]
    p_qa1.alignment = PP_ALIGN.CENTER
    p_qa1.text = "Thank You!"
    p_qa1.font.size = Pt(22)
    p_qa1.font.bold = True
    p_qa1.font.color.rgb = TEXT_WHITE

    p_qa2 = qa_tf.add_paragraph()
    p_qa2.alignment = PP_ALIGN.CENTER
    p_qa2.text = "We welcome your questions and evaluation discussion."
    p_qa2.font.size = Pt(14)
    p_qa2.font.color.rgb = BLUE_ACCENT

    # Save to all destination paths
    for p in output_paths:
        os.makedirs(os.path.dirname(p), exist_ok=True)
        prs.save(p)
        print(f"Saved simplified PPTX to: {p}")

if __name__ == "__main__":
    artifact_dir = r"C:\Users\Admin\.gemini\antigravity\brain\7c7a5e96-3a5e-4f98-9ddf-eecf22a77086"
    workspace_dir = r"C:\Users\Admin\.gemini\antigravity\scratch\nexus_os"

    destinations = [
        os.path.join(artifact_dir, "NEXUS_OS_Project_Presentation.pptx"),
        os.path.join(workspace_dir, "NEXUS_OS_Project_Presentation.pptx")
    ]
    create_deck(destinations)
