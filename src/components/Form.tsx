import {
  useForm,
  UseFormProps,
  UseFormReturn,
  SubmitHandler,
  FieldValues,
  FormProvider,
  Resolver,
} from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { ZodType } from 'zod'
import { ReactNode, FormHTMLAttributes } from 'react'
import { clsx } from 'clsx'

interface FormProps<TFormValues extends FieldValues>
  extends Omit<FormHTMLAttributes<HTMLFormElement>, 'onSubmit' | 'children'> {
  schema?: ZodType<TFormValues>
  defaultValues?: UseFormProps<TFormValues>['defaultValues']
  onSubmit: SubmitHandler<TFormValues>
  children: (methods: UseFormReturn<TFormValues>) => ReactNode
  formProps?: Omit<UseFormProps<TFormValues>, 'defaultValues' | 'resolver'>
  className?: string
}

export function Form<TFormValues extends FieldValues>({
  schema,
  defaultValues,
  onSubmit,
  children,
  className,
  formProps,
  ...rest
}: FormProps<TFormValues>) {
  const methods = useForm<TFormValues>({
    defaultValues,
    resolver: schema ? (zodResolver(schema as never) as Resolver<TFormValues>) : undefined,
    mode: 'onTouched',
    ...formProps,
  })

  return (
    <FormProvider {...methods}>
      <form
        onSubmit={methods.handleSubmit(onSubmit)}
        className={clsx('space-y-4', className)}
        noValidate
        {...rest}
      >
        {children(methods)}
      </form>
    </FormProvider>
  )
}
