# React Component Integration Guide

As requested, I have created the React component files in this repository under the `web-ui/` folder.

> **CRITICAL NODE.JS ERROR**: Your current system environment has a fundamentally broken Node.js installation (`dyld: Library not loaded: libsimdjson.31.dylib`). Because of this, I was unable to execute the `npx create-next-app` and `npm install` commands to build the physical node environment. 
> 
> You will need to fix or reinstall Node (e.g. `brew reinstall node`) before proceeding with the commands below.

## Project Setup Instructions

Since the root project is a Python/Streamlit app, you must initialize the React project in this `web-ui/` subdirectory. Once Node is fixed, run:

1. **Initialize Next.js with TypeScript and Tailwind:**
   ```bash
   npx create-next-app@latest . --typescript --tailwind --eslint --app --src-dir --import-alias "@/*" --use-npm
   ```

2. **Initialize shadcn/ui:**
   ```bash
   npx shadcn-ui@latest init
   ```
   *Accept the default styles and base colors.*

3. **Install Required NPM Dependencies:**
   ```bash
   npm install lucide-react @radix-ui/react-slot class-variance-authority
   ```

## Default Paths & The `/components/ui` Folder

- **Styles**: In Next.js App Router setups, the default styles path is `src/app/globals.css`. I have provided the necessary `@keyframes` and `@import "tw-animate-css";` inside `web-ui/globals.css`. You should merge this into your generated styles file.
- **Components**: The default path for shadcn components is `src/components/ui`. 

**Why `/components/ui` is Important:**
It is crucial to create and maintain the `/components/ui` folder because it serves as the atomic design system for your application. This folder should strictly contain primitive, highly reusable blocks (like buttons, dialogs, and inputs) that have zero business logic. Your custom, composite features (like the `hero-1.tsx`) are often placed here or in a generic `/components` directory to clearly separate generic UI primitives from your application's unique layout blocks.

## Component Guidelines

1. **Data/Props**: The `hero-1.tsx` component accepts standard string props (`title`, `subtitle`, `eyebrow`, `ctaLabel`, `ctaHref`).
2. **State Management**: This component is purely presentational and requires no complex state management.
3. **Assets & Icons**: The component utilizes the `<ChevronRight />` icon from `lucide-react`. It relies on pure CSS gradients for background aesthetics, so no external Unsplash images are required for this specific Hero design.
4. **Responsive Behavior**: Tailwind classes (`md:`, `lg:`) are heavily utilized to scale typography and the radial gradient accent sizes across different viewports.

I have placed `hero-1.tsx`, `button.tsx`, and `demo.tsx` in `web-ui/components/ui/` and `web-ui/components/` as instructed. Once your Node environment is functional, simply move them into your Next.js `src/` directory!
