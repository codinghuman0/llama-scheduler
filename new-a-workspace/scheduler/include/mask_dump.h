/* SPDX-License-Identifier: GPL-2.0 */
#ifndef NEW_A_MASK_DUMP_H
#define NEW_A_MASK_DUMP_H

#include <ctype.h>
#include <errno.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include "new_a.h"

static inline int new_a_parse_mask_limit(const char *text, unsigned int *limit)
{
	unsigned long last = 0;
	bool found = false;

	for (;;) {
		char *end;
		unsigned long first, high;

		if (!isdigit((unsigned char)*text))
			return -EINVAL;
		errno = 0;
		first = strtoul(text, &end, 10);
		if (errno || first >= NEW_A_MAX_CPUS || (found && first <= last))
			return -ERANGE;
		high = first;
		text = end;
		if (*text == '-') {
			text++;
			if (!isdigit((unsigned char)*text))
				return -EINVAL;
			errno = 0;
			high = strtoul(text, &end, 10);
			if (errno || high < first || high >= NEW_A_MAX_CPUS)
				return -ERANGE;
			text = end;
		}
		last = high;
		found = true;
		if (*text != ',')
			break;
		text++;
	}
	while (isspace((unsigned char)*text))
		text++;
	if (*text)
		return -EINVAL;
	*limit = (unsigned int)last + 1;
	return 0;
}

static inline unsigned int new_a_mask_weight(const __u64 *bits, unsigned int limit)
{
	unsigned int weight = 0;

	for (unsigned int cpu = 0; cpu < limit && cpu < NEW_A_MAX_CPUS; cpu++)
		weight += !!(bits[cpu / 64] & (1ULL << (cpu % 64)));
	return weight;
}

static inline bool new_a_mask_complete(const __u64 *bits, unsigned int limit,
				      unsigned int expected, int error)
{
	return limit && limit <= NEW_A_MAX_CPUS && !error &&
	       new_a_mask_weight(bits, limit) == expected;
}

static inline void new_a_print_mask(FILE *output, const __u64 *bits, unsigned int mask_bits)
{
	bool comma = false;

	fputc('[', output);
	for (unsigned int cpu = 0; cpu < mask_bits && cpu < NEW_A_MAX_CPUS; cpu++) {
		if (!(bits[cpu / 64] & (1ULL << (cpu % 64))))
			continue;
		fprintf(output, "%s%u", comma ? "," : "", cpu);
		comma = true;
	}
	fputc(']', output);
}

#endif
