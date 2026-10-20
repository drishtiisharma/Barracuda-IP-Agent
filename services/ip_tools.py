import ipaddress


def parse_ip(value):
    return ipaddress.ip_address(value.strip())


def parse_ip_list(raw):
    """Split pasted text into (valid_unique, invalid, duplicates)."""
    valid, invalid, duplicates, seen = [], [], [], set()
    for token in raw.replace(",", " ").replace(";", " ").split():
        try:
            item = str(parse_ip(token))
        except ValueError:
            invalid.append(token)
            continue
        if item in seen:
            duplicates.append(item)
        else:
            seen.add(item)
            valid.append(item)
    return valid, invalid, duplicates


def parse_range(start, end, max_count):
    first, last = parse_ip(start), parse_ip(end)
    if first.version != last.version:
        raise ValueError("From IP and To IP must use the same address family.")
    if int(last) < int(first):
        raise ValueError("To IP must be greater than or equal to From IP.")
    count = int(last) - int(first) + 1
    if count > max_count:
        raise ValueError(f"Range contains {count} IPs; maximum allowed is {max_count}.")
    return [str(ipaddress.ip_address(n)) for n in range(int(first), int(last) + 1)]
