import os, time

def generate_checklist():
    base = "/mnt/d/explore/road-map.md"
    checklist_file = os.path.join(base, "CHECKLIST_PROGRESS_PEKERJAAN.md")

    cats = {
        "01-Core-Foundations": "t_1c34908b",
        "02-Programming-Languages": "t_9edb8cbf",
        "03-Frontend-and-Mobile": "t_0307bbae",
        "04-Backend-and-Database": "t_34c78a3f",
        "05-DevOps-Cloud-and-SRE": "t_d3509546",
        "06-Architecture-and-System-Design": "t_9d100b0f",
        "07-Quality-and-Security": "t_b243b511",
        "08-AI-Data-and-Autonomous-Agents": "t_40e62aa7"
    }

    lines = []
    lines.append("# 📋 CHECKLIST DETAIL PROGRESS PENYELESAIAN MATERI ROADMAP.SH\n\n")
    lines.append(f"> Terakhir Diperbarui: {time.ctime()}\n")
    lines.append("> Standar Mutu: Setiap track wajib memiliki README Silabus + 10 BAB Lengkap (BAB 01 - BAB 10) + Hands-on Lab sesuai aturan **GEMINI.md**.\n")
    lines.append("> Status Simbol: `[x]` = Tuntas 10 BAB Penuh | `[ ]` = Belum Lengkap (Dalam Proses)\n\n")

    total_tracks = 0
    total_completed_tracks = 0
    cat_blocks = []

    for cat, tid in cats.items():
        cat_dir = os.path.join(base, cat)
        if not os.path.exists(cat_dir): continue
        subdirs = sorted([s for s in os.listdir(cat_dir) if os.path.isdir(os.path.join(cat_dir, s))])
        
        cat_done = 0
        block = []
        
        for s in subdirs:
            s_path = os.path.join(cat_dir, s)
            babs = sorted([d for d in os.listdir(s_path) if d.startswith('BAB-')])
            is_full = len(babs) >= 10
            total_tracks += 1
            if is_full:
                cat_done += 1
                total_completed_tracks += 1
                mark = "[x]"
                status_text = f"**SELESAI LENGKAP ({len(babs)}/10 BAB)**"
            else:
                mark = "[ ]"
                status_text = f"Baru ada {len(babs)}/10 BAB"
            
            block.append(f"- {mark} **{s}** — {status_text}\n")
            if len(babs) > 0:
                bab_sample = ", ".join(babs[:4]) + ("..." if len(babs) > 4 else "")
                block.append(f"  - *Bab fisik:* `{bab_sample}`\n")
        
        cat_status = "DONE" if cat_done == len(subdirs) and len(subdirs) > 0 else "TODO"
        header = f"## 📁 {cat} (Kanban: `{tid}` | Status: `{cat_status}`)\n"
        header += f"**Ringkasan Kategori:** {cat_done}/{len(subdirs)} Track Selesai 10 BAB ({(cat_done/len(subdirs)*100 if subdirs else 0):.1f}%)\n\n"
        cat_blocks.append(header + "".join(block) + "\n---\n\n")

    summary_header = f"## 📊 RINGKASAN PROGRESS GLOBAL\n"
    summary_header += f"- **Total Track Terdaftar:** {total_tracks} Track Resmi\n"
    summary_header += f"- **Track Selesai 10 BAB Penuh:** {total_completed_tracks}/{total_tracks} Track ({(total_completed_tracks/total_tracks*100):.1f}%)\n"
    summary_header += f"- **Track Belum Lengkap (Antrean):** {total_tracks - total_completed_tracks} Track\n"
    summary_header += f"- **Kanban Parent Ticket:** `t_cec9e3a1`\n\n---\n\n"

    final_content = "".join(lines) + summary_header + "".join(cat_blocks)
    with open(checklist_file, "w", encoding="utf-8") as f:
        f.write(final_content)

if __name__ == "__main__":
    generate_checklist()
    print("Checklist markdown generated successfully.")
