import time

totaltime = time.time()
import sys
import healpy as hp
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.colors as col
from matplotlib import rcParams, rc
from c3postproc.tools import arcmin2rad

print("Importtime:", (time.time() - totaltime))


def Plotter(
    input,
    dataset,
    nside,
    auto,
    min,
    max,
    minmax,
    rng,
    colorbar,
    lmax,
    fwhm,
    mask,
    mfill,
    sig,
    remove_dipole,
    logscale,
    size,
    white_background,
    darkmode,
    pdf,
    cmap,
    title,
    unit,
    verbose,
):
    rcParams["backend"] = "pdf" if pdf else "Agg"
    rcParams["legend.fancybox"] = True
    rcParams["lines.linewidth"] = 2
    rcParams["savefig.dpi"] = 300
    rcParams["axes.linewidth"] = 1

    masked = False

    if darkmode:
        rcParams["text.color"] = "white"  # axes background color
        rcParams["axes.facecolor"] = "white"  # axes background color
        rcParams["axes.edgecolor"] = "white"  # axes edge color
        rcParams["axes.labelcolor"] = "white"
        rcParams["xtick.color"] = "white"  # color of the tick labels
        rcParams["ytick.color"] = "white"  # color of the tick labels
        rcParams["grid.color"] = "white"  # grid color
        rcParams[
            "legend.facecolor"
        ] = "inherit"  # legend background color (when 'inherit' uses axes.facecolor)
        rcParams[
            "legend.edgecolor"
        ] = "white"  # legend edge color (when 'inherit' uses axes.edgecolor)

    rc("text.latex", preamble=r"\usepackage{sfmath}")

    # Which signal to plot
    print("----------------------------------")
    print("Plotting " + input)

    #######################
    ####   READ MAP   #####
    #######################
    starttime = time.time()

    if input.endswith(".fits"):
        # Make sure its the right shape for indexing
        # This is a really dumb way of doing it
        dats = [0, 0, 0]
        map_exists = False
        for i in sig:
            try:
                dats[i] = hp.ma(hp.read_map(input, field=i, verbose=False))
                nsid = hp.npix2nside(len(dats[i]))
                map_exists = True
            except:
                print(f"Signal {i} not found in data, skipping")
                continue

        if map_exists == False:
            print(f"{input} does not contain a {sig} signal. Breaking.")
            sys.exit()

        maps = np.array(dats)
        outfile = input.replace(".fits", "")

    elif input.endswith(".h5"):
        from c3postproc.commands import h5map2fits
        from c3postproc.tools import alm2fits_tool

        if dataset.endswith("alm"):
            print("Converting alms to map")
            maps, nsid, lmax, fwhm, outfile = alm2fits_tool(
                input, dataset, nside, lmax, fwhm, save=False
            )

        elif dataset.endswith("map"):
            print("Reading map from h5")
            maps, nsid, lmax, outfile = h5map2fits(input, dataset, save=False)

        else:
            print("Dataset not found. Breaking.")
            print(f"Does {input}/{dataset} exist?")
            sys.exit()
    else:
        print("Dataset not found. Breaking.")
        sys.exit()

    print("Map reading: ", (time.time() - starttime)) if verbose else None
    print("nside", nsid, "total file shape", maps.shape)

    # Iterate through I, Q and U
    for polt in sig:
        m = maps[polt]

        ############
        #  SMOOTH  #
        ############
        if fwhm > 0 and input.endswith(".fits"):
            print(f"Smoothing fits map to {fwhm} degrees fwhm")
            m = hp.smoothing(m, fwhm=arcmin2rad(fwhm), lmax=lmax)

        ############
        # UD_GRADE #
        ############
        if nside is not None and input.endswith(".fits"):
            print(f"UDgrading map from {nsid} to {nside}")
            m = hp.ud_grade(m, nside)
        else:
            nside = nsid

        ########################
        #### remove dipole #####
        ########################
        if remove_dipole:
            starttime = time.time()
            print("Removing dipole")
            dip_mask_name = remove_dipole
            # Mask map for dipole estimation
            m_masked = hp.ma(m)
            m_masked.mask = np.logical_not(hp.read_map(dip_mask_name))

            # Fit dipole to masked map
            mono, dip = hp.fit_dipole(m_masked)
            print(f"Dipole vector: {dip}")
            print(f"Dipole amplitude: {np.sqrt(np.sum(dip ** 2))}")

            # Create dipole template
            nside = int(nside)
            ray = range(hp.nside2npix(nside))
            vecs = hp.pix2vec(nside, ray)
            dipole = np.dot(dip, vecs)

            # Subtract dipole map from data
            m = m - dipole
            print(f"Dipole removal : {(time.time() - starttime)}") if verbose else None

        #######################
        #### Auto-param   #####
        #######################
        # ttl, unt and cmb are temporary variables for title, unit and colormap
        if auto:
            ttl, ticks, ticklabels, unt, cmp, lgscale, format_ticks= get_params(
                m, outfile, polt,
            )
        else:
            ttl = ""
            unt = ""
            rng = "auto"
            ticks = [False, False]
            ticklabels = [False, False]
            cmp = "planck"
            lgscale = False

        # If range has been specified, set.
        if rng:
            if rng == "auto":
                format_ticks = False
                if minmax:
                    mn = np.min(m)
                    mx = np.max(m)
                else:
                    mx = np.percentile(m, 97.5)
                    mn = np.percentile(m, 2.5)
                if min is False:
                    min = mn
                if max is False:
                    max = mx
            else:
                rng = float(rng)
                min = -rng
                max = rng

        # If min and max have been specified, set.
        if min is not False:
            ticks[0] = float(min)
            ticklabels[0] = str(min)

        if max is not False:
            ticks[-1] = float(max)
            ticklabels[-1] = str(max)

        ##########################
        #### Plotting Params #####
        ##########################

        # Upper right title
        if not title:
            title = ttl

        # Unit under colorbar
        if not unit:
            unit = unt

        # Image size -  ratio is always 1/2
        xsize = 2000
        ysize = int(xsize / 2.0)

        #######################
        ####   logscale   #####
        #######################
        # Some maps turns on logscale automatically
        # -logscale command overwrites this
        if logscale == None:
            logscale = lgscale

        if logscale:
            print("Applying logscale")
            starttime = time.time()

            m = np.log10(0.5 * (m + np.sqrt(4.0 + m * m)))
            m = np.maximum(np.minimum(m, ticks[-1]), ticks[0])

            print("Logscale", (time.time() - starttime)) if verbose else None

        ######################
        #### COLOR SETUP #####
        ######################
        # Chose colormap manually
        if cmap == None:
            # If not defined autoset or goto planck
            cmap = cmp

        print(f"Setting colormap to {cmap}")
        if cmap == "planck":
            from pathlib import Path

            cmap = Path(__file__).parent / "parchment1.dat"
            cmap = col.ListedColormap(np.loadtxt(cmap) / 255.0)
        else:
            cmap = plt.get_cmap(cmap)
        
    

        #######################
        ####  Projection? #####
        #######################
        theta = np.linspace(np.pi, 0, ysize)
        phi = np.linspace(-np.pi, np.pi, xsize)
        longitude = np.radians(np.linspace(-180, 180, xsize))
        latitude = np.radians(np.linspace(-90, 90, ysize))

        # project the map to a rectangular matrix xsize x ysize
        PHI, THETA = np.meshgrid(phi, theta)
        grid_pix = hp.ang2pix(nside, THETA, PHI)

        ######################
        ######## Mask ########
        ######################
        if mask:
            print(f"Masking using {mask}")
            masked = True

            # Apply mask
            hp.ma(m)
            m.mask = np.logical_not(hp.read_map(mask))

            # Don't know what this does, from paperplots by Zonca.
            grid_mask = m.mask[grid_pix]
            grid_map = np.ma.MaskedArray(m[grid_pix], grid_mask)

            if mfill:
                cmap.set_bad(mfill)  # color of missing pixels
                # cmap.set_under("white") # color of background, necessary if you want to use
                # using directly matplotlib instead of mollview has higher quality output
        else:
            grid_map = m[grid_pix]

        ######################
        #### Formatting ######
        ######################
        from matplotlib.projections.geo import GeoAxes

        class ThetaFormatterShiftPi(GeoAxes.ThetaFormatter):
            """Shifts labelling by pi
            Shifts labelling from -180,180 to 0-360"""

            def __call__(self, x, pos=None):
                if x != 0:
                    x *= -1
                if x < 0:
                    x += 2 * np.pi
                return GeoAxes.ThetaFormatter.__call__(self, x, pos)

        sizes = get_sizes(size)
        for width in sizes:
            print("Plotting size " + str(width))
            height = width / 2.0

            # Make sure text doesnt change with colorbar
            height *= 1.275 if colorbar else 1

            ################
            ##### font #####
            ################
            if width > 12.0:
                fontsize = 8
            elif width == 12.0:
                fontsize = 7
            else:
                fontsize = 6

            fig = plt.figure(figsize=(cm2inch(width), cm2inch(height)))

            ax = fig.add_subplot(111, projection="mollweide")

            # rasterized makes the map bitmap while the labels remain vectorial
            # flip longitude to the astro convention
            image = plt.pcolormesh(
                longitude[::-1],
                latitude,
                grid_map,
                vmin=ticks[0],
                vmax=ticks[-1],
                rasterized=True,
                cmap=cmap,
            )
            # graticule
            ax.set_longitude_grid(60)
            ax.xaxis.set_major_formatter(ThetaFormatterShiftPi(60))

            if width < 10:
                ax.set_latitude_grid(45)
                ax.set_longitude_grid_ends(90)

            ################
            ### COLORBAR ###
            ################
            if colorbar:
                # colorbar
                from matplotlib.ticker import FuncFormatter
                cb = fig.colorbar(
                    image,
                    orientation="horizontal",
                    shrink=0.3,
                    pad=0.08,
                    ticks=ticks,
                    format=FuncFormatter(fmt),
                )

                # Don't format ticks if autoset
                if format_ticks:
                   cb.ax.set_xticklabels(ticklabels)

                cb.ax.xaxis.set_label_text(unit)
                cb.ax.xaxis.label.set_size(fontsize)
                #cb.ax.minorticks_on()

                cb.ax.tick_params(
                    which="both", axis="x", direction="in", labelsize=fontsize
                )
                cb.ax.xaxis.labelpad = 4  # -11
                # workaround for issue with viewers, see colorbar docstring
                cb.solids.set_edgecolor("face")

            # remove longitude tick labels
            ax.xaxis.set_ticklabels([])
            # remove horizontal grid
            ax.xaxis.set_ticks([])
            ax.yaxis.set_ticklabels([])
            ax.yaxis.set_ticks([])
            plt.grid(True)

            #############
            ## TITLE ####
            #############
            plt.text(
                6.0, 1.3, r"%s" % title, ha="center", va="center", fontsize=fontsize,
            )

            ##############
            #### SAVE ####
            ##############
            plt.tight_layout()
            filetype = "pdf" if pdf else "png"
            tp = (
                False if white_background else True
            )  # Turn on transparency unless told otherwise

            ##############
            ## filename ##
            ##############
            filename = []
            filename.append(f"{str(int(fwhm))}arcmin") if fwhm > 0 else None
            filename.append("cb") if colorbar else None
            filename.append("masked") if masked else None
            filename.append("dark") if darkmode else None

            nside_tag = "_n" + str(int(nside))
            if nside_tag in outfile:
                outfile = outfile.replace(nside_tag, "")
            
            fn = outfile + f"_{get_signallabel(polt)}_w{str(int(width))}" + nside_tag

            for i in filename:
                fn += f"_{i}"
            fn += f".{filetype}"

            starttime = time.time()
            plt.savefig(
                fn,
                bbox_inches="tight",
                pad_inches=0.02,
                transparent=tp,
                format=filetype,
            )
            print("Savefig", (time.time() - starttime)) if verbose else None

            plt.close()
            print("Totaltime:", (time.time() - totaltime)) if verbose else None


def get_params(m, outfile, polt):
    print()
    logscale = False

    # Everything listed here will be recognized
    # If tag is found in output file, use template
    cmb_tags = ["cmb", "BP_cmb"]
    chisq_tags = ["chisq"]
    synch_tags = ["synch_c", "synch_amp", "BP_synch"]
    dust_tags = ["dust_c", "dust_amp", "BP_dust"]
    ame_tags = ["ame_c", "ame_amp", "ame1_c", "ame1_amp", "BP_ame"]
    ff_tags = ["ff_c", "ff_amp", "BP_freefree"]
    co10_tags = ["co10", "co-100"]
    co21_tags = ["co21", "co-217"]
    co32_tags = ["co32", "co-353"]
    hcn_tags = ["hcn"]
    dust_T_tags = ["dust_T", "dust_Td"]
    dust_beta_tags = ["dust_beta"]
    synch_beta_tags = ["synch_beta"]
    ff_Te_tags = ["ff_T_e", "ff_Te"]
    ff_EM_tags = ["ff_EM"]
    res_tags = ["residual_", "res_"]
    tod_tags = ["Smap"]
    freqmap_tags = ["BP_030", "BP_044", "BP_070"]
    ignore_tags = ["radio_"]

    sl = get_signallabel(polt)
    startcolor = 'black'
    endcolor = 'white'
    format_ticks = True # If min and max are autoset, dont do this.

    if tag_lookup(cmb_tags, outfile,):
        print("----------------------------------")
        print(f"Plotting CMB signal {sl}")
        
        title = r"$" + sl + "$" + r"$_{\mathrm{CMB}}$"

        if polt > 0:
            vmin = -2
            vmid = 0
            vmax = 2
        else:
            vmin = -300
            vmid = 0
            vmax = 300

        tmin = str(vmin)
        tmid = str(vmid)
        tmax = str(vmax)

        ticks = [vmin, vmid, vmax]
        ticklabels = [tmin, tmid, tmax]

        unit = r"$\mu\mathrm{K}_{\mathrm{CMB}}$"

        from pathlib import Path

        color = Path(__file__).parent / "parchment1.dat"
        cmap = col.ListedColormap(np.loadtxt(color) / 255.0)

    elif tag_lookup(chisq_tags, outfile):
        title = r"$\chi^2$ " + sl

        if polt > 0:
            vmin = 0
            vmax = 32
        else:
            vmin = 0
            vmax = 76

        tmin = str(vmin)
        tmax = str(vmax)

        ticks = [vmin, vmax]
        ticklabels = [tmin, tmax]

        print("----------------------------------")
        print("Plotting chisq with vmax = " + str(vmax) + " " + sl)

        unit = ""
        cmap = col.LinearSegmentedColormap.from_list("own2", ["black", "white"])

    elif tag_lookup(synch_tags, outfile):
        print("----------------------------------")
        print(f"Plotting Synchrotron {sl}")
        title = r"$" + sl + "$" + r"$_{\mathrm{s}}$ "
        if polt > 0:
            # BP uses 30 GHz ref freq for pol
            vmin = -np.log10(50)
            vmax = np.log10(50)
            tmin = str(-50)
            tmax = str(50)
            logscale = True

            vmid = 0
            tmid = "0"
            ticks = [vmin, vmid, vmax]
            ticklabels = [tmin, tmid, tmax]

            
            col1 = "darkgoldenrod"
            col2 = "darkgreen"
            cmap = col.LinearSegmentedColormap.from_list(
                "own2", [endcolor, col1, startcolor, col2, endcolor]
            )
            unit = r"$\mu\mathrm{K}_{\mathrm{RJ}}$"
        else:
            # BP uses 408 MHz GHz ref freq
            vmin = np.log10(10*10**6)
            vmid1 = np.log10(30*10**6)
            vmid2 = np.log10(100*10**6)
            vmax = np.log10(300*10**6)

            tmin = str(r"$10$")
            tmid1 = str(r"$30$")
            tmid2 = str(r"$100$")
            tmax = str(r"$300$")
    
            logscale = True
            cmap = col.LinearSegmentedColormap.from_list(
                "own2", ["black", "green", "white"]
            )

            ticks = [vmin,vmid1, vmid2, vmax,]
            ticklabels = [tmin, tmid1, tmid2, tmax, ]

            unit = r"$\mathrm{K}_{\mathrm{RJ}}$"

    elif tag_lookup(ff_tags, outfile):
        print("----------------------------------")
        print("Plotting freefree")

        vmin = 0  # 0
        vmid = np.log10(100)
        vmax = np.log10(10000)  # 1000

        tmin = str(0)
        tmid = str(r"$10^2$")
        tmax = str(r"$10^4$")

        ticks = [vmin, vmid, vmax]
        ticklabels = [tmin, tmid, tmax]

        unit = r"$\mu\mathrm{K}_{\mathrm{RJ}}$"
        title = r"$" + sl + "$" + r"$_{\mathrm{ff}}$"
        logscale = True
        cmap = col.LinearSegmentedColormap.from_list("own2", ["black", "Navy", "white"])

    elif tag_lookup(dust_tags, outfile):
        print("----------------------------------")
        print("Plotting Thermal dust" + " " + sl)
        title = r"$" + sl + "$" + r"$_{\mathrm{d}}$ "
        if polt > 0:
            vmin = -np.log10(100)
            vmid = 0
            vmax = np.log10(100)

            tmin = str(-100)
            tmid = 0
            tmax = str(100)

            logscale = True

            col1 = "deepskyblue"
            col2 = "blue"
            col3 = "firebrick"
            col4 = "darkorange"
            cmap = col.LinearSegmentedColormap.from_list(
                "own2", [endcolor, col1, col2, startcolor, col3, col4, endcolor]
            )

        else:
            vmin = 0
            vmid = np.log10(100)
            vmax = np.log10(10000)

            tmin = str(0)
            tmid = str(r"$10^2$")
            tmax = str(r"$10^4$")

            logscale = True
            cmap = plt.get_cmap("gist_heat")

        ticks = [vmin, vmid, vmax]
        ticklabels = [tmin, tmid, tmax]

        unit = r"$\mu\mathrm{K}_{\mathrm{RJ}}$"

    elif tag_lookup(ame_tags, outfile):
        print("----------------------------------")
        print("Plotting AME")

        vmin = 0  # 0
        vmid = np.log10(100)
        vmax = np.log10(10000)  # 1000

        tmin = r"$0$"
        tmid = r"$10^2$"
        tmax = r"$10^4$"

        ticks = [vmin, vmid, vmax]
        ticklabels = [tmin, tmid, tmax]

        unit = r"$\mu\mathrm{K}_{\mathrm{RJ}}$"
        title = r"$" + sl + "$" + r"$_{\mathrm{ame}}$"
        logscale = True
        cmap = col.LinearSegmentedColormap.from_list(
            "own2", ["black", "DarkOrange", "white"]
        )

    elif tag_lookup(co10_tags, outfile):
        print("----------------------------------")
        print("Plotting CO10")
        vmin = 0
        vmid = np.log10(10)
        vmax = np.log10(100)

        tmin = str(0)
        tmid = str(10)
        tmax = str(100)

        ticks = [vmin, vmid, vmax]
        ticklabels = [tmin, tmid, tmax]

        unit = r"$\mathrm{K}_{\mathrm{RJ}}\, \mathrm{km}/\mathrm{s}$"
        title = r"$" + sl + "$" + r"$_{\mathrm{CO10}}$"
        logscale = True
        cmap = plt.get_cmap("gray")

    elif tag_lookup(co21_tags, outfile):
        print("----------------------------------")
        print("Plotting CO21")
        vmin = 0
        vmid = 1
        vmax = 2
        tmin = str(0)
        tmid = str(10)
        tmax = str(100)

        ticks = [vmin, vmid, vmax]
        ticklabels = [tmin, tmid, tmax]

        unit = r"$\mathrm{K}_{\mathrm{RJ}}\, \mathrm{km}/\mathrm{s}$"
        title = r"$" + sl + "$" + r"$_{\mathrm{CO21}}$"
        logscale = True
        cmap = plt.get_cmap("gray")

    elif tag_lookup(co32_tags, outfile):
        print("----------------------------------")
        print("Plotting 32")
        vmin = 0
        vmid = 1
        vmax = 2  # 0.5
        tmin = str(0)
        tmid = str(10)
        tmax = str(100)

        ticks = [vmin, vmid, vmax]
        ticklabels = [tmin, tmid, tmax]

        unit = r"$\mathrm{K}_{\mathrm{RJ}}\, \mathrm{km}/\mathrm{s}$"
        title = r"$" + sl + "$" + r"$_{\mathrm{CO32}}$"
        logscale = True
        cmap = plt.get_cmap("gray")

    elif tag_lookup(hcn_tags, outfile):
        print("----------------------------------")
        print("Plotting HCN")
        vmin = -14
        vmax = -10
        tmin = str(0.01)
        tmax = str(100)

        ticks = [vmin, vmax]
        ticklabels = [tmin, tmax]

        unit = r"$\mathrm{K}_{\mathrm{RJ}}\, \mathrm{km}/\mathrm{s}$"
        title = r"$" + sl + "$" + r"$_{\mathrm{HCN}}$"
        logscale = True
        cmap = plt.get_cmap("gray")

    elif tag_lookup(ame_tags, outfile):
        print("----------------------------------")
        print("Plotting AME nu_p")

        vmin = 17
        vmax = 23
        tmin = str(vmin)
        tmax = str(vmax)

        ticks = [vmin, vmax]
        ticklabels = [tmin, tmax]

        unit = "GHz"
        title = r"$\nu_{ame}$"
        cmap = plt.get_cmap("bone")

    # SPECTRAL INDEX MAPS
    elif tag_lookup(dust_T_tags, outfile):
        print("----------------------------------")
        print("Plotting Thermal dust Td")

        title = r"$" + sl + "$ " + r"$T_d$ "

        vmin = 14
        vmax = 30
        tmin = str(vmin)
        tmax = str(vmax)

        ticks = [vmin, vmax]
        ticklabels = [tmin, tmax]

        unit = r"$\mathrm{K}$"
        cmap = plt.get_cmap("bone")

    elif tag_lookup(dust_beta_tags, outfile):
        print("----------------------------------")
        print("Plotting Thermal dust beta")

        title = r"$" + sl + "$ " + r"$\beta_d$ "

        vmin = 1.3
        vmax = 1.8
        tmin = str(vmin)
        tmax = str(vmax)
        ticks = [vmin, vmax]
        ticklabels = [tmin, tmax]

        unit = ""
        cmap = plt.get_cmap("bone")

    elif tag_lookup(synch_beta_tags, outfile):
        print("----------------------------------")
        print("Plotting Synchrotron beta")

        title = r"$" + sl + "$ " + r"$\beta_s$ "

        vmin = -4.0
        vmax = -1.5
        tmin = str(vmin)
        tmax = str(vmax)

        ticks = [vmin, vmax]
        ticklabels = [tmin, tmax]

        unit = ""
        cmap = plt.get_cmap("bone")

    elif tag_lookup(ff_Te_tags, outfile):
        print("----------------------------------")
        print("Plotting freefree T_e")

        vmin = 5000
        vmax = 8000
        tmin = str(vmin)
        tmax = str(vmax)

        ticks = [vmin, vmax]
        ticklabels = [tmin, tmax]

        unit = r"$\mathrm{K}$"
        title = r"$T_{e}$"
        cmap = plt.get_cmap("bone")

    elif tag_lookup(ff_EM_tags, outfile):
        print("----------------------------------")
        print("Plotting freefree EM MIN AND MAX VALUES UPDATE!")

        vmax = np.percentile(m, 97.5)
        vmin = np.percentile(m, 2.5)

        tmid = str(vmid)
        tmax = str(vmax)

        ticks = [vmin, vmax]
        ticklabels = [tmin, tmax]

        format_ticks = False

        unit = r"$\mathrm{K}$"
        title = r"$T_{e}$"
        cmap = plt.get_cmap("bone")

    #################
    # RESIDUAL MAPS #
    #################

    elif tag_lookup(res_tags, outfile):
        from re import findall

        print("----------------------------------")
        print("Plotting residual map" + " " + sl)

        if "res_" in outfile:
            tit = str(findall(r"res_(.*?)_", outfile)[0])
        else:
            tit = str(findall(r"residual_(.*?)_", outfile)[0])

        title = fr"{tit} " + r"  $" + sl + "$"

        vmin = -10
        vmid = 0
        vmax = 10
        tmin = str(vmin)
        tmid = str(vmid)
        tmax = str(vmax)

        unit = r"$\mu\mathrm{K}$"
        cmap = col.ListedColormap(np.loadtxt(color) / 255.0)

        from pathlib import Path

        color = Path(__file__).parent / "parchment1.dat"

        if "545" in outfile:
            vmin = -1e2
            vmax = 1e2
            tmin = str(vmin)
            tmax = str(vmax)
            unit = r"$\mathrm{MJy/sr}$"
        elif "857" in outfile:
            vmin = -0.05  # -1e4
            vmax = 0.05  # 1e4
            tmin = str(vmin)
            tmax = str(vmax)
            unit = r"$\mathrm{MJy/sr}$"

        ticks = [vmin, vmid, vmax]
        ticklabels = [tmin, tmid, tmax]

    ############
    # TOD MAPS #
    ############

    elif tag_lookup(tod_tags, outfile):
        from re import findall

        print("----------------------------------")
        print("Plotting Smap map" + " " + sl)

        tit = str(findall(r"tod_(.*?)_Smap", outfile)[0])
        title = fr"{tit} " + r"  $" + sl + "$"

        vmin = -0.2
        vmid = 0
        vmax = 0.2
        tmin = str(vmin)
        tmid = str(vmid)
        tmax = str(vmax)

        unit = r"$\mu\mathrm{K}$"
        cmap = col.ListedColormap(np.loadtxt(color) / 255.0)

        from pathlib import Path

        color = Path(__file__).parent / "parchment1.dat"

        ticks = [vmin, vmid, vmax]
        ticklabels = [tmin, tmid, tmax]
    ############
    # FREQMAPS #
    ############

    elif tag_lookup(freqmap_tags, outfile):
        from re import findall

        print("----------------------------------")
        print("Plotting Frequency map" + " " + sl)

        tit = str(findall(r"BP_(.*?)_", outfile)[0])
        title = fr"{tit} " + r"  $" + sl + "$"

        vmax = np.percentile(m, 97.5)
        vmid = 0.0
        vmin = np.percentile(m, 2.5)
    
        tmin = str(vmin)
        tmid = str(vmid)
        tmax = str(vmax)
        format_ticks = False

        unit = r"$\mu\mathrm{K}$"
        
        cmap ="planck"

        ticks = [vmin, vmid, vmax]
        ticklabels = [tmin, tmid, tmax]

    ############################
    # Not idenified or ignored #
    ############################
    elif tag_lookup(ignore_tags, outfile):
        print(
            f'{outfile} is on the ignore list, under tags {ignore_tags}. Remove from "ignore_tags" in plotter.py. Breaking.'
        )
        sys.exit()
    else:
        print("----------------------------------")
        print("Map not recognized, plotting with min and max values")
        vmax = np.percentile(m, 97.5)
        vmin = np.percentile(m, 2.5)
    
        tmin = str(vmin)
        tmax = str(vmax)
        format_ticks = False

        ticks = [vmin, vmax]
        ticklabels = [tmin, tmax]
        unit = ""
        title = r"$" + sl + "$"

        from pathlib import Path

        color = Path(__file__).parent / "parchment1.dat"
        cmap = col.ListedColormap(np.loadtxt(color) / 255.0)

    return title, ticks, ticklabels, unit, cmap, logscale, format_ticks

def get_signallabel(x):
    if x == 0:
        return "I"
    if x == 1:
        return "Q"
    if x == 2:
        return "U"
    return str(x)

def get_sizes(size):
    sizes = []
    if "s" in size:
        sizes.append(8.8)
    if "m" in size:
        sizes.append(12.0)
    if "l" in size:
        sizes.append(18.0)
    return sizes


def fmt(x, pos):
    """
    Format color bar labels
    """
    if abs(x) > 1e4:
        a, b = f"{x:.2e}".split("e")
        b = int(b)
        return fr"${a} \cdot 10^{{{b}}}$"
    elif abs(x) > 1e2:
        return fr"${int(x):d}$"
    elif abs(x) > 1e1:
        return fr"${x:.1f}$"
    elif abs(x) == 0.0:
        return fr"${x:.1f}$"
    else:
        return fr"${x:.2f}$"


def cm2inch(cm):
    return cm * 0.393701


def tag_lookup(tags, outfile):
    return any(e in outfile for e in tags)
