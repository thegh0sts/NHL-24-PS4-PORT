
/* ---- NHL 24: the System V red zone, moved out of reach of Windows exception frames ----
 *
 * PS4 code is System V: a function may keep data in the 128 bytes below its stack pointer (the
 * red zone) without moving rsp; nothing else may write there. Windows has no red zone: when an
 * instruction faults, the kernel writes the exception information right below rsp, and the
 * runtime's own handler runs below that. The GPU memory tracking makes guest accesses to watched
 * pages fault on purpose (handled, then the guest continues), so any such fault inside a
 * function that is using its red zone erased its data (NHL 24: FUN_07660830, the renderer's
 * draw-list sort, read back a pointer it had saved at [rsp-0x28] as 0 after a tracking fault in
 * the same loop, and crashed).
 *
 * The patch: every instruction that addresses memory at a negative displacement from rsp
 * ([rsp-d], [rsp+index*s-d], lea of either) addresses REDZONE_SHIFT bytes lower instead. All of a
 * function's red-zone accesses move by the same amount, so they still meet each other (and a
 * pointer taken with lea still points at the same, moved, data); positive displacements (the
 * caller's arguments, the function's own frame) are not touched. Exception frames and handlers
 * use far less than REDZONE_SHIFT, and every guest stack has STACK_MARGIN (256 KiB) of committed
 * room below its size (runtime_thread.c; the main thread's 16 MiB stack too).
 *
 * The instruction grows (disp8 -> disp32), so it runs from a stub: a jmp at the site to the
 * rewritten instruction(s) and back, as the deterministic FP stubs do (following instructions go
 * along when the site is shorter than the jmp; never a branch target, call, or rcp/rsqrt site).
 * Branch targets: direct jumps, RIP-relative addresses, the image's pointers, and the entries of
 * the PIC jump tables clang emits for switches (a lea of a table of 32-bit offsets). */
#define REDZONE_SHIFT 0x10000
int runtime_redzone_enabled(void) {
    static int value = -1;
    if (value < 0) {
        const char *forced = getenv("BB_REDZONE_SHIFT");
#ifdef _WIN32
        value = !(forced && forced[0] == '0');
#else
        value = forced && forced[0] == '1'; /* Linux signal frames skip the red zone already */
#endif
    }
    return value;
}
static int fp_site(const ZydisDecodedInstruction *in) {
    switch (in->mnemonic) {
    case ZYDIS_MNEMONIC_RCPPS: case ZYDIS_MNEMONIC_VRCPPS: case ZYDIS_MNEMONIC_RSQRTPS: case ZYDIS_MNEMONIC_VRSQRTPS:
    case ZYDIS_MNEMONIC_RCPSS: case ZYDIS_MNEMONIC_VRCPSS: case ZYDIS_MNEMONIC_RSQRTSS: case ZYDIS_MNEMONIC_VRSQRTSS: return 1;
    default: return 0;
    }
}
/* An instruction whose ModRM memory operand is [rsp + (index*scale) + negative displacement]. */
static int redzone_site(const ZydisDecodedInstruction *in, const ZydisDecodedOperand *op, const unsigned char *code) {
    if (in->encoding != ZYDIS_INSTRUCTION_ENCODING_LEGACY && in->encoding != ZYDIS_INSTRUCTION_ENCODING_VEX) return 0;
    if (in->attributes & (ZYDIS_ATTRIB_HAS_SEGMENT | ZYDIS_ATTRIB_IS_RELATIVE)) return 0;
    if (!in->raw.modrm.offset || (in->raw.modrm.mod != 1 && in->raw.modrm.mod != 2) || (code[in->raw.modrm.offset] & 7) != 4) return 0;
    if ((in->raw.disp.size != 8 && in->raw.disp.size != 32) || in->raw.disp.value >= 0 || in->raw.disp.offset != in->raw.modrm.offset + 2)
        return 0;
    if (in->address_width != 64) return 0; /* an rcp/rsqrt of red-zone data moves too (it then keeps the CPU's result) */
    switch (in->mnemonic) {
    case ZYDIS_MNEMONIC_PUSH: case ZYDIS_MNEMONIC_POP: case ZYDIS_MNEMONIC_ENTER: case ZYDIS_MNEMONIC_LEAVE: return 0;
    default: break;
    }
    if (in->meta.category == ZYDIS_CATEGORY_COND_BR || in->meta.category == ZYDIS_CATEGORY_UNCOND_BR ||
        in->meta.category == ZYDIS_CATEGORY_CALL || in->meta.category == ZYDIS_CATEGORY_RET)
        return 0;
    int found = 0;
    for (unsigned i = 0; i < in->operand_count; ++i) {
        /* never one that changes rsp itself (lea rsp, [rsp-n] moves the stack) */
        if (op[i].type == ZYDIS_OPERAND_TYPE_REGISTER && (op[i].actions & ZYDIS_OPERAND_ACTION_MASK_WRITE) &&
            (op[i].reg.value == ZYDIS_REGISTER_RSP || op[i].reg.value == ZYDIS_REGISTER_ESP || op[i].reg.value == ZYDIS_REGISTER_SP))
            return 0;
        if (i < in->operand_count_visible && op[i].type == ZYDIS_OPERAND_TYPE_MEMORY && op[i].mem.base == ZYDIS_REGISTER_RSP) found = 1;
    }
    return found;
}
/* The instruction with its displacement REDZONE_SHIFT lower (always disp32). */
static unsigned char *emit_shifted(unsigned char *q, const unsigned char *code, const ZydisDecodedInstruction *in) {
    const unsigned mo = in->raw.modrm.offset, after = in->raw.disp.offset + in->raw.disp.size / 8;
    memcpy(q, code, mo);
    q += mo;
    *q++ = (uint8_t)((code[mo] & 0x3f) | 0x80); /* mod 10: disp32 */
    *q++ = code[mo + 1];                          /* SIB */
    const int32_t d = (int32_t)in->raw.disp.value - REDZONE_SHIFT;
    memcpy(q, &d, 4);
    q += 4;
    memcpy(q, code + after, in->length - after); /* immediates */
    return q + (in->length - after);
}
/* Entries of a switch table (int32 offsets from the table) that land in [start, end). */
static uint64_t mark_jump_table(Scan *c, uint64_t size, uint64_t table, uint64_t start, uint64_t end) {
    uint64_t n = 0;
    for (; n < 4096 && table + 4 * n + 4 <= size; ++n) {
        int32_t entry;
        memcpy(&entry, c->image + table + 4 * n, 4);
        const uint64_t target = table + (uint64_t)(int64_t)entry;
        if (target < start || target >= end) break;
        mark(c, target, size);
    }
    return n;
}

enum { REDZONE_STUB = 128 };
uint64_t runtime_redzone_patch_image(unsigned char *image, uint64_t size, const uint64_t *seg_address, const uint64_t *seg_size,
                                     const uint64_t *seg_flags, uint64_t segments, const uint64_t *pointers, uint64_t pointer_count,
                                     void *(*map_near)(size_t), RuntimeFpStats *stats) {
    memset(stats, 0, sizeof(*stats));
    ZydisDecoder decoder;
    ZydisDecoderInit(&decoder, ZYDIS_MACHINE_MODE_LONG_64, ZYDIS_STACK_WIDTH_64);
    Scan c = {image, seg_address, seg_size, seg_flags, segments, calloc(size / 8 + 1, 1)};
    uint64_t *sites = NULL, count = 0, capacity = 0, range_count = 0;
    if (!c.targets) return 0;
    for (uint64_t i = 0; i < pointer_count; ++i) mark(&c, pointers[i], size);
    Range *ranges = unwind_ranges(&c, size, &range_count);
    if (!range_count) {
        free(ranges);
        if (!(ranges = calloc(segments ? segments : 1, sizeof(*ranges)))) { free(c.targets); return 0; }
        for (uint64_t g = 0; g < segments; ++g)
            if (seg_flags[g] & 1) ranges[range_count++] = (Range){seg_address[g], seg_address[g] + seg_size[g]};
    } else stats->functions = range_count;
    /* Pass 1: the sites, direct targets and switch-table entries. */
    for (uint64_t r = 0; r < range_count; ++r) {
        for (uint64_t at = ranges[r].start, end = ranges[r].end; at < end;) {
            ZydisDecodedInstruction in;
            ZydisDecodedOperand op[ZYDIS_MAX_OPERAND_COUNT];
            if (!ZYAN_SUCCESS(ZydisDecoderDecodeFull(&decoder, image + at, end - at, &in, op))) { ++at; continue; }
            const uint64_t next = at + in.length;
            if (in.raw.imm[0].is_relative) mark(&c, next + (uint64_t)in.raw.imm[0].value.s, size);
            if (in.raw.modrm.offset && in.raw.modrm.mod == 0 && in.raw.modrm.rm == 5 && in.raw.disp.size == 32) {
                const uint64_t addressed = next + (uint64_t)in.raw.disp.value;
                mark(&c, addressed, size);
                if (in.mnemonic == ZYDIS_MNEMONIC_LEA) stats->displaced += mark_jump_table(&c, size, addressed, ranges[r].start, ranges[r].end);
            }
            if (redzone_site(&in, op, image + at)) {
                if (count == capacity) {
                    uint64_t *grown = realloc(sites, (capacity = capacity ? capacity * 2 : 65536) * 2 * sizeof(*sites));
                    if (!grown) { free(sites); free(ranges); free(c.targets); return 0; }
                    sites = grown;
                }
                sites[2 * count] = at; sites[2 * count++ + 1] = end;
            }
            at = next;
        }
    }
    free(ranges);
    stats->found = count;
    const size_t area_size = (size_t)count * REDZONE_STUB;
    unsigned char *area = count ? map_near(area_size) : NULL;
    if (!area) { stats->unpatched = count; free(sites); free(c.targets); return 0; }
    unsigned char *p = area;
    uint64_t covered_until = 0;
    /* Pass 2: a stub per site, with the instructions it displaces. */
    for (uint64_t i = 0; i < count; ++i) {
        const uint64_t at = sites[2 * i], end = sites[2 * i + 1];
        if (at < covered_until) { ++stats->patched; continue; } /* rewritten inside the previous stub */
        unsigned char *stub = p, *q = p;
        uint64_t length = 0;
        int ok = 1;
        while (ok && length < JMP) {
            ZydisDecodedInstruction in;
            ZydisDecodedOperand op[ZYDIS_MAX_OPERAND_COUNT];
            const uint64_t here = at + length;
            if (here >= end || (length && is_target(&c, here)) || (size_t)(q - stub) > REDZONE_STUB - 40 ||
                !ZYAN_SUCCESS(ZydisDecoderDecodeFull(&decoder, image + here, end - here, &in, op))) { ok = 0; break; }
            if (redzone_site(&in, op, image + here)) q = emit_shifted(q, image + here, &in);
            else if (length && length + in.length >= JMP && relative_jump(&in)) {
                const unsigned char *target = image + here + in.length + in.raw.imm[0].value.s;
                if (in.opcode == 0xeb || in.opcode == 0xe9) *q++ = 0xe9;
                else { *q++ = 0x0f; *q++ = (uint8_t)(0x80 | (in.opcode & 0x0f)); }
                int32_t d = 0;
                if (!rel32(q + 4, target, &d)) ok = 0;
                memcpy(q, &d, 4);
                q += 4;
            } else if (!length || !movable(&in) || fp_site(&in)) ok = 0;
            else {
                memcpy(q, image + here, in.length);
                if (in.raw.modrm.offset && in.raw.modrm.mod == 0 && in.raw.modrm.rm == 5) { /* RIP-relative */
                    int32_t d;
                    if (!rel32(q + in.length, image + here + in.length + in.raw.disp.value, &d)) ok = 0;
                    else memcpy(q + in.raw.disp.offset, &d, 4);
                }
                q += in.length;
            }
            length += in.length;
        }
        int32_t back = 0, to_stub = 0;
        if (ok) {
            q[0] = 0xe9;
            ok = rel32(q + 5, image + at + length, &back) && rel32(image + at + JMP, stub, &to_stub);
        }
        if (!ok) {
            if (stats->unpatched++ < 8) printf("Red zone: the access at image offset 0x%" PRIx64 " is kept (the next instructions cannot move)\n", at);
            continue;
        }
        memcpy(q + 1, &back, 4);
        p = q + 5;
        image[at] = 0xe9;
        memcpy(image + at + 1, &to_stub, 4);
        memset(image + at + JMP, 0xcc, length - JMP);
        ++stats->patched;
        covered_until = at + length;
    }
    stats->stub_bytes = (uint64_t)(p - area);
    if (platform_protect(area, area_size, PROT_READ | PROT_EXEC)) {
        fputs("STOP: red zone: cannot make the stubs executable\n", stderr);
        exit(21);
    }
    free(sites); free(c.targets);
    return stats->patched;
}
