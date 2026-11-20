import test from 'node:test';
import assert from 'node:assert/strict';
import { isVirtualOrLinkLocal, lanUrls } from './start.mjs';

test('isVirtualOrLinkLocal filters link-local addresses (169.254.x.x)', () => {
  assert.equal(isVirtualOrLinkLocal('169.254.0.1'), true);
  assert.equal(isVirtualOrLinkLocal('169.254.120.45'), true);
});

test('isVirtualOrLinkLocal filters VirtualBox subnet (192.168.56.x)', () => {
  assert.equal(isVirtualOrLinkLocal('192.168.56.1'), true);
  assert.equal(isVirtualOrLinkLocal('192.168.56.102'), true);
});

test('isVirtualOrLinkLocal filters virtual adapters by interface name', () => {
  assert.equal(isVirtualOrLinkLocal('192.168.56.1', 'VirtualBox Host-Only Network'), true);
  assert.equal(isVirtualOrLinkLocal('172.28.0.1', 'vEthernet (WSL)'), true);
  assert.equal(isVirtualOrLinkLocal('172.18.96.1', 'vEthernet (Default Switch)'), true);
  assert.equal(isVirtualOrLinkLocal('10.0.75.1', 'Hyper-V Virtual Ethernet Adapter'), true);
  assert.equal(isVirtualOrLinkLocal('172.17.0.1', 'docker0'), true);
  assert.equal(isVirtualOrLinkLocal('192.168.49.2', 'Docker Desktop'), true);
  assert.equal(isVirtualOrLinkLocal('192.168.120.1', 'VMware Network Adapter VMnet1'), true);
  assert.equal(isVirtualOrLinkLocal('127.0.0.1', 'Loopback Pseudo-Interface 1'), true);
});

test('isVirtualOrLinkLocal does NOT blanket ban 172.16-31.x.x on normal interfaces (e.g. Wi-Fi / LAN hotspot)', () => {
  assert.equal(isVirtualOrLinkLocal('172.16.0.1', 'Wi-Fi'), false);
  assert.equal(isVirtualOrLinkLocal('172.20.10.5', 'iPhone USB'), false);
  assert.equal(isVirtualOrLinkLocal('172.20.10.2', 'Wi-Fi'), false);
  assert.equal(isVirtualOrLinkLocal('172.31.255.254', 'Ethernet'), false);
});

test('isVirtualOrLinkLocal keeps legitimate local Wi-Fi / LAN addresses', () => {
  assert.equal(isVirtualOrLinkLocal('192.168.1.50', 'Ethernet'), false);
  assert.equal(isVirtualOrLinkLocal('192.168.0.101', 'Wi-Fi'), false);
  assert.equal(isVirtualOrLinkLocal('10.0.0.15', 'en0'), false);
});

test('lanUrls with mocked os.networkInterfaces() filters VirtualBox and returns only real LAN URLs', () => {
  const mockInterfaces = {
    'Ethernet (Unplugged)': [
      { address: '169.254.12.34', family: 'IPv4', internal: false },
    ],
    'VirtualBox Host-Only Ethernet Adapter': [
      { address: '192.168.56.1', family: 'IPv4', internal: false },
    ],
    'vEthernet (Default Switch)': [
      { address: '172.28.0.1', family: 'IPv4', internal: false },
    ],
    'VMware Network Adapter VMnet8': [
      { address: '192.168.120.1', family: 'IPv4', internal: false },
    ],
    'docker0': [
      { address: '172.17.0.1', family: 'IPv4', internal: false },
    ],
    'Loopback Pseudo-Interface 1': [
      { address: '127.0.0.1', family: 'IPv4', internal: true },
    ],
    'Wi-Fi': [
      { address: '192.168.1.150', family: 'IPv4', internal: false },
    ],
    'iPhone USB': [
      { address: '172.20.10.2', family: 'IPv4', internal: false },
    ],
  };

  const urls = lanUrls(4173, mockInterfaces);
  assert.deepEqual(urls, [
    'http://192.168.1.150:4173',
    'http://172.20.10.2:4173',
  ]);
});
