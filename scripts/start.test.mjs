import test from 'node:test';
import assert from 'node:assert/strict';
import { isVirtualOrLinkLocal } from './start.mjs';

test('isVirtualOrLinkLocal filters link-local addresses (169.254.x.x)', () => {
  assert.equal(isVirtualOrLinkLocal('169.254.0.1'), true);
  assert.equal(isVirtualOrLinkLocal('169.254.120.45'), true);
});

test('isVirtualOrLinkLocal filters VirtualBox adapters (192.168.56.x)', () => {
  assert.equal(isVirtualOrLinkLocal('192.168.56.1'), true);
  assert.equal(isVirtualOrLinkLocal('192.168.56.102'), true);
});

test('isVirtualOrLinkLocal filters Docker bridge / container subnets (172.16.x.x - 172.31.x.x)', () => {
  assert.equal(isVirtualOrLinkLocal('172.16.0.1'), true);
  assert.equal(isVirtualOrLinkLocal('172.17.0.1'), true);
  assert.equal(isVirtualOrLinkLocal('172.20.10.5'), true);
  assert.equal(isVirtualOrLinkLocal('172.31.255.254'), true);
  // 172.15.x.x or 172.32.x.x are outside the private /12 block
  assert.equal(isVirtualOrLinkLocal('172.15.0.1'), false);
  assert.equal(isVirtualOrLinkLocal('172.32.0.1'), false);
});

test('isVirtualOrLinkLocal keeps legitimate local Wi-Fi / LAN addresses', () => {
  assert.equal(isVirtualOrLinkLocal('192.168.1.50'), false);
  assert.equal(isVirtualOrLinkLocal('192.168.0.101'), false);
  assert.equal(isVirtualOrLinkLocal('10.0.0.15'), false);
});
