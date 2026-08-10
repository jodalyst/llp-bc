# lab-bc-client

This is the client-side source for AY2026 llp-bc build infrastructure in 6.1903. Assuming you are in "our system", this piece of software allows you to run builds for and flash the ESP32C3-based RISCV development kit we use in the class..

# Installation

The llp-bc client software requires only Python. Greater than 3.12 is recommended, though I think back to 3.10 will probably work. Create a virtual Python environment. I _strongly_ recommend you do that rather than use system Python. You can do this quite easily with the following code which makes a virtual environment called `61903_python`:

```
python3 -m venv 61903_python
```

While not strictly necessary, you can also run the virtual environment creation with the `--copies` modifier to ensure the virtual environment is completely isolated from your system Python.

Once created, activate your Python virtual environment with:

```
source 61903_python/bin/activate
```

You should then be able to install this library by running the command:

```
pip install git+https://github.com/jodalyst/llp-bc
```

EZPZ.

# Usage

After installation in your terminal, you can use `llp-bc` at any time if you have your Python virtual environment activated.

## Configuration (Do One Time After Installation)

Prior to your first run on `llp-bc`, make sure to run:

```
llp-bc configure
```

And provide your kerberos (lowercase), MIT ID, the llp-bc server endpoint (for Fall 2026 6.1903 this is likely `eecs-digital-60.mit.edu/llp-bc`). These will be used to verify your submissions to the build server. You only need to run `configure` once after the installation. The system should verify your credentials when you submit them. If you get a error/issue, read what it says...maybe you aren't in the class so your credentials aren't on the machine? Maybe you typed in the wrong server endpoint?

## Running Builds

Any time you want to build, you can simply do:

```
llp-bc compile {project}
```

For example, if you are in a project directory, you would run:

```
llp-bc compile ./
```

The output of a build, if successful, will show up in a `build` folder (including the appropriate bit file and metadata).

## Flashing your Microcontroller

If you have a good compilation and are currently in your project, assuming there is `build` folder present, then you can simply run:

```
llp-bc flash ./
```

There are some optional arguments that I'll write something about, but for our class, just the standard `llp-bc flash ./` should be good enough.

# Archiving

`llp-bc` will automatically make zipped snapshots of your project and its results every time you run it. These will be placed into the `_history` folder and be named using the timestamp of the submission. I added this since you students tend to be horrendous with version control.  Note, this archive can get large when you're doing many builds so feel free to delete files if you ever want.

# Provenance

This project is based on an original version developed by Jay Lang as part of his [2023 M.Eng thesis at MIT](https://dspace.mit.edu/handle/1721.1/151412?show=full) for original deployment in [6.205/6.111](https://fpga.mit.edu/6205/F25). It was then largely rewritten from the ground-up in Python for portability and maintainability. Nothing wrong with the original, just we learned a lot and things needed changin'.  This current repo (`llp-bc`) is a variant of that ongoing project, different enough from the one for 6.205 that I just made a new project.

For security reasons, other portions of the current `llp-bc` project (server and worker source code) are private, but if interested, reach out to me at jodalyst@mit.edu.
