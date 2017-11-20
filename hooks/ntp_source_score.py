#!/usr/bin/python3

# Copyright (c) 2017 Canonical Ltd
# Author: Paul Gear

# This module runs ntpdate in test mode against the provided list of sources
# in order to determine this node's suitability as an NTP server, based on the
# number of reachable sources, and the network delay in reaching them.  Up to
# MAX_THREADS (default 32) threads will be spawned to run ntpdate, in order
# to minimise the time taken to calculate a score.

# A main method is included to allow this module to be called separately from
# juju hooks for diagnostic purposes.  It has no dependencies on juju,
# charmhelpers, or the other modules in this charm.

import argparse
import math
import queue
import random
import statistics
import subprocess
import threading
import time

rand = random.SystemRandom()
MAX_THREADS = 32


def rms(l):
    """Return the root mean square of the list"""
    if len(l) > 0:
        squares = [x ** 2 for x in l]
        return math.sqrt(statistics.mean(squares))
    else:
        return float('nan')


def run_cmd(cmd):
    """Run the output, return a list of lines returned; ignore errors"""
    lines = []
    try:
        output = subprocess.check_output(cmd.split(), stderr=subprocess.DEVNULL).decode('UTF-8')
        lines = output.split('\n')
    except Exception:
        pass
    return lines


def get_source_delays(source):
    """Run ntpdate on the source, which may resolve to multiple addresses;
    return the list of delay values. This can take several seconds, depending
    on bandwidth and distance of the sources."""
    delays = []
    cmd = 'ntpdate -d -t 0.2 ' + source
    for line in run_cmd(cmd):
        fields = line.split()
        if len(fields) >= 2 and fields[0] == 'delay':
            delay = float(fields[1].split(',')[0])
            if delay > 0:
                delays.append(delay)
    return delays


def worker(num, src, dst, debug=False):
    """Thread worker for parallelising ntpdate runs.  Gets host name
    from src queue and places host and delay list in dst queue."""
    if debug:
        print('[%d] Starting' % (num,))
    while True:
        host = src.get()
        if host is None:
            break

        # lower-numbered threads sleep for a shorter time, on average
        s = rand.random() * num / MAX_THREADS
        if debug:
            print('[%d] Sleeping %.3f' % (num, s))
        time.sleep(s)

        if debug:
            print('[%d] Getting results for [%s]' % (num, host))
        delays = get_source_delays(host)
        src.task_done()
        if len(delays):
            result = (host, delays)
            dst.put(result)


def get_delay_score(delay):
    """Take a delay in seconds and return a score.  Under most sane NTP setups
    will return a value between 0 and 10, where 10 is better and 0 is worse."""
    return -math.log(delay)


def start_workers(threads, num_threads, src, dst, debug=False):
    """Start all of the worker threads."""
    for i in range(num_threads):
        t = threading.Thread(target=worker, args=(i, src, dst, debug))
        t.start()
        threads.append(t)


def stop_workers(threads, src):
    """Send the workers a None object, causing them to stop work.
    We enqueue one stop object for each worker."""
    for i in range(len(threads)):
        src.put(None)


def calculate_score(delays):
    """Return the rms, mean, standard deviation, and overall
    score for the passed list of delay values."""
    score = 0
    if len(delays) > 0:
        r = rms(delays)
        m = statistics.mean(delays)
        s = statistics.pstdev(delays, m)
        source_score = get_delay_score(r)
        score += source_score
    else:
        r = m = s = score = 0
    return (r, m, s, score)


def calculate_results(q, verbose=False):
    """Get the scores for all the hosts.
    Return a hash of hosts and their cumulative scores."""
    results = {}
    while not q.empty():
        (host, delays) = q.get()
        (rms, mean, stdev, score) = calculate_score(delays)
        delaystrings = [str(x) for x in delays]
        if verbose:
            print('%s score=%.3f rms=%.3f mean=%.3f stdevp=%.3f [%s]' %
                  (host, score, rms, mean, stdev, ", ".join(delaystrings)))
        if host in results:
            results[host] += score
        else:
            results[host] = score
    return results


def wait_workers(threads):
    """Wait for the given list of threads to complete."""
    for t in threads:
        t.join()


def run_checks(hosts, debug=False, numthreads=None, verbose=False):
    """Perform a check of the listed hosts.
    Can take several seconds per host."""
    sources = queue.Queue()
    results = queue.Queue()
    threads = []
    for h in hosts:
        sources.put(h)
    if numthreads is None:
        numthreads = min(len(hosts), MAX_THREADS)
    start_workers(threads, numthreads, sources, results, debug)
    sources.join()
    stop_workers(threads, sources)
    # wait_workers(threads)
    return calculate_results(results, verbose)


def get_source_score(hosts, debug=False, numthreads=None, verbose=False):
    """Check NTP connectivity to the given list of sources - return a single overall score"""
    results = run_checks(hosts, debug, numthreads, verbose)
    if results is None:
        return 0

    total = 0
    for host in results:
        total += results[host]
    return total


def display_results(results):
    """Sort the hash by value.  Print the results."""
    # http://stackoverflow.com/a/2258273
    result = sorted(results.items(), key=lambda x: x[1], reverse=True)
    for i in result:
        print("%s %.3f" % (i[0], i[1]))


def get_args():
    parser = argparse.ArgumentParser(description='Get NTP server/peer/pool scores')
    parser.add_argument('--debug', '-d', action='store_true', help='Enable thread debug output')
    parser.add_argument('--verbose', '-v', action='store_true', help='Display scoring detail')
    parser.add_argument('hosts', nargs=argparse.REMAINDER, help='List of hosts to check')
    return parser.parse_args()


if __name__ == '__main__':
    args = get_args()
    results = run_checks(args.hosts, debug=args.debug, verbose=args.verbose)
    if results:
        display_results(results)
