# Glossary

Terms and definitions used in Contree MCP.

## A

**Async Execution**
: Running operations without waiting for completion. Use `wait=false` and poll with `get_operation` or `wait_operations`.

## D

**Directory State**
: A snapshot of local files synced with `rsync`. Identified by `directory_state_id`.

**Disposable**
: When `disposable=true` (default), filesystem changes are discarded after command execution.

## I

**Image**
: An immutable filesystem snapshot. Identified by UUID.

**Image Lineage**
: The parent-child relationships between images. View with `contree://image/{uuid}/lineage`.

## M

**MCP (Model Context Protocol)**
: The protocol used for AI agent tool communication.

**MicroVM**
: A lightweight virtual machine used for isolated command execution.

## O

**Operation**
: A running or completed task (command execution or image import). Identified by `operation_id`.

## R

**Result Image**
: The image UUID returned when running with `disposable=false` and filesystem changes occur.

**Root Image**
: An image imported from a container registry, with no parent.

## T

**Tag**
: A human-readable name for an image (e.g., `python:3.11`). Tags can point to different UUIDs over time.

## U

**UUID**
: Universally Unique Identifier. The primary way to reference images and operations.
