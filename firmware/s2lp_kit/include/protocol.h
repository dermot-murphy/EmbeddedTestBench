/**
 * @file protocol.h
 * @brief The host link of the ETB S2-LP kit firmware (#84): limits and record kinds.
 *
 * One command per line, answered by one line: "ok ..." or "err <reason>".
 * While receiving, the firmware also sends one line per record, unasked:
 *
 *   f <seq> <time_us> <length> <registers hex> <payload hex>   a frame
 *   r <seq> <time_us> <irq status hex>                         a rejection
 *
 * The sequence number counts every record, sent or dropped, so a gap in it
 * is a record the board could not queue. Times are the board's microsecond
 * timer when the radio's interrupt was taken, modulo 2^32.
 */

#ifndef PROTOCOL_H
#define PROTOCOL_H

/** Version of this line protocol, reported by "id". */
#define PROTO_VERSION           (1U)

/** Largest payload the S2-LP's receive FIFO holds, in bytes. */
#define PROTO_MAX_PAYLOAD       (128U)

/** Most registers read after each frame. */
#define PROTO_MAX_REGISTERS     (8U)

/** Longest command line accepted, without its line end. */
#define PROTO_LINE_MAX          (300U)

/** Record kind: a frame received intact. */
#define PROTO_KIND_FRAME        ('f')

/** Record kind: a reception the radio discarded (CRC, filter, FIFO error). */
#define PROTO_KIND_REJECT       ('r')

#endif /* PROTOCOL_H */
